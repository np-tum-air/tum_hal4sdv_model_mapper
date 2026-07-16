import argparse
import base64
import io
import os

from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

from instance_validator import validate_files


load_dotenv()


base_prompt_ecore = (
    "You are converting a given model instance to comply with a target "
    "Ecore metamodel. Map as many elements as possible from the model "
    "instance to the target metamodel. The result must be an Ecore XMI "
    "model instance compliant with the target metamodel."
)


base_prompt_sysml = (
    "You are an expert in SysML v2 model transformation. "
    "Convert the given source model instance into a SysML v2 textual instance "
    "that conforms to the provided target SysML model definition. "
    "Preserve as much semantic information as possible while ensuring that the "
    "generated model conforms to the target definitions. "
    "Generate the output as a SysML v2 instance using the same structure as the "
    "target model, including a package declaration, required imports, a typed "
    "top-level part usage, nested 'part redefines' statements, and "
    "'attribute redefines' assignments for property values. "
    "Create a package containing typed top-level part usages using the syntax. "
    "Reuse only definitions declared in the target SysML model. "
    "Return only the resulting SysML v2 model without explanations, comments, "
    "or Markdown code fences."
)



def imageToContentBody(img: Image.Image) -> dict:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/png;base64,{b64}"
        },
    }


def getResponse(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    images: list | None = None,
) -> str:
    if images is None:
        images = []

    content = [imageToContentBody(img) for img in images]
    content.append(
        {
            "type": "text",
            "text": user_prompt,
        }
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": content,
            },
        ],
        model=model,
    )

    response_content = chat_completion.choices[0].message.content

    if response_content is None:
        raise RuntimeError("The model returned an empty response.")

    return response_content


def remove_markdown_fences(response: str) -> str:
    response = response.strip()

    if response.startswith("```"):
        response_lines = response.splitlines()

        # Remove opening fence, such as ```xml.
        response_lines = response_lines[1:]

        # Remove closing fence.
        if response_lines and response_lines[-1].strip() == "```":
            response_lines = response_lines[:-1]

        response = "\n".join(response_lines).strip()

    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Map a model instance to a target metamodel."
    )

    parser.add_argument(
        "first_metamodel_content",
        type=str,
        help="Path to the input model instance.",
    )

    parser.add_argument(
        "second_metamodel_content",
        type=str,
        help="Path to the target metamodel.",
    )

    parser.add_argument(
        "target_language",
        type=str,
        choices=["ecore", "sysml"],
        help="Target metamodel variant: ecore or sysml.",
    )

    args = parser.parse_args()

    first_metamodel_path = Path(args.first_metamodel_content)
    second_metamodel_path = Path(args.second_metamodel_content)

    with first_metamodel_path.open("r", encoding="utf-8") as file:
        first_metamodel_content = file.read()

    with second_metamodel_path.open("r", encoding="utf-8") as file:
        second_metamodel_content = file.read()

    user_prompt = dedent(
    f"""\
        Merge the following two source metamodels into one unified target metamodel.

        First source metamodel:

        {first_metamodel_content}

        Second source metamodel:

        {second_metamodel_content}

        Target modeling language:

        {args.target_language}

        Preserve all compatible classes, attributes, references, inheritance
        relationships, multiplicities, containment relationships, and data types.

        Identify equivalent concepts and merge them instead of creating duplicates.
        Integrate complementary concepts from both metamodels.
        Resolve naming and structural conflicts consistently.
        Preserve the semantics of both source metamodels as much as possible.

        Generate one valid metamodel in the requested target modeling language.

        Return only the resulting metamodel without explanations, comments,
        or Markdown code fences.
        """
    )

    if args.target_language == "ecore":
        system_prompt = base_prompt_ecore
    else:
        system_prompt = base_prompt_sysml

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),    
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    response = getResponse(
        client=client,
        #model="google/gemma-4-31B-it",
        model="Qwen/Qwen3.5-122B-A10B",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    response = remove_markdown_fences(response)

    if args.target_language == "ecore":
        output_file = Path("metamodel_merged.ecore")

        with output_file.open("w", encoding="utf-8") as file:
            file.write(response)

        print(f"Generated model saved to: {output_file}")

    else:
        output_file = Path("metamodel_merged.sysml")

        with output_file.open("w", encoding="utf-8") as file:
            file.write(response)

        print(f"Generated model saved to: {output_file}")

