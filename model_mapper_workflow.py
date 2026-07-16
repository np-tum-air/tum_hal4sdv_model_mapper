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
"""
base_prompt_sysml = (
    "You are an expert in SysML v2 model transformation. "
    "Convert the given source model instance into a SysML v2 TEXTUAL INSTANCE MODEL "
    "that conforms to the provided target SysML model definition. "
    "The target model already contains all required definitions. "
    "Generate ONLY instance model elements. "
    "Never generate 'part def', 'attribute def', 'port def', or any other definition. "
    "Create a package containing typed top-level part usages using the syntax "
    "'part <instanceName> : <DefinitionName> { ... }'. "
    "Represent inherited components using 'part redefines', inherited ports using "
    "'port redefines', and inherited properties using 'attribute redefines'. "
    "Reuse only definition names, part names, port names, and attribute names "
    "declared in the target SysML model. "
    "Preserve the hierarchy and property values from the source model. "
    "Return only valid SysML v2 textual syntax without explanations, comments, "
    "or Markdown code fences."
)
"""

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


"""
base_prompt_sysml = (
    "You are converting a given model instance to comply with a target "
    "SysML model definition. Map as many elements as possible from the "
    "model instance to the target model. Return a valid SysML model instance."
)
"""


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
        "instance_model",
        type=str,
        help="Path to the input model instance.",
    )

    parser.add_argument(
        "target_metamodel",
        type=str,
        help="Path to the target metamodel.",
    )

    parser.add_argument(
        "variant",
        type=str,
        choices=["ecore", "sysml"],
        help="Target metamodel variant: ecore or sysml.",
    )

    args = parser.parse_args()

    instance_model_path = Path(args.instance_model)
    target_metamodel_path = Path(args.target_metamodel)

    with instance_model_path.open("r", encoding="utf-8") as file:
        instance_model_content = file.read()

    with target_metamodel_path.open("r", encoding="utf-8") as file:
        target_metamodel_content = file.read()

    user_prompt = dedent(
        f"""\
        Map the following model instance:

        {instance_model_content}

        to comply with the following target metamodel:

        {target_metamodel_content}

        Return only the resulting model instance without explanations
        or Markdown code fences.
        """
    )

    if args.variant == "ecore":
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

    if args.variant == "ecore":
        output_file = instance_model_path.with_name(
            f"{instance_model_path.stem}_mapped.xmi"
        )

        with output_file.open("w", encoding="utf-8") as file:
            file.write(response)

        print(f"Generated model saved to: {output_file}")

    else:
        output_file = instance_model_path.with_name(
            f"{instance_model_path.stem}_mapped.sysml"
        )

        with output_file.open("w", encoding="utf-8") as file:
            file.write(response)

        print(f"Generated model saved to: {output_file}")
