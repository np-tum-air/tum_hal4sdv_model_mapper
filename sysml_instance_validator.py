import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


PRIMITIVE_TYPES = {
    "Boolean",
    "String",
    "Integer",
    "Natural",
    "Real",
    "Rational",
}


@dataclass
class AttributeDefinition:
    name: str
    type_name: str


@dataclass
class FeatureDefinition:
    name: str
    type_name: str
    feature_kind: str
    lower: int = 1
    upper: Optional[int] = 1


@dataclass
class TypeDefinition:
    name: str
    kind: str
    attributes: dict[str, AttributeDefinition] = field(default_factory=dict)
    features: dict[str, FeatureDefinition] = field(default_factory=dict)


@dataclass
class FeatureInstance:
    name: str
    kind: str
    declared_type: Optional[str] = None
    values: dict[str, str] = field(default_factory=dict)
    children: list["FeatureInstance"] = field(default_factory=list)


@dataclass
class ValidationIssue:
    severity: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


def remove_comments(text: str) -> str:
    """Remove // and /* ... */ comments."""

    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)

    return text


def find_matching_brace(text: str, opening_position: int) -> int:
    """Return the position of the matching closing brace."""

    depth = 0
    in_string = False
    escaped = False

    for position in range(opening_position, len(text)):
        character = text[position]

        if escaped:
            escaped = False
            continue

        if character == "\\" and in_string:
            escaped = True
            continue

        if character == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1

            if depth == 0:
                return position

    raise ValueError(
        f"No matching closing brace for position {opening_position}."
    )


def extract_top_level_blocks(
    text: str,
    pattern: re.Pattern[str],
) -> list[tuple[re.Match[str], str]]:
    """
    Extract blocks matching a declaration pattern.

    Nested declarations are skipped because only matches occurring at the
    current text level are returned.
    """

    blocks: list[tuple[re.Match[str], str]] = []
    position = 0

    while position < len(text):
        match = pattern.search(text, position)

        if match is None:
            break

        opening_brace = text.find("{", match.start())

        if opening_brace == -1:
            break

        closing_brace = find_matching_brace(text, opening_brace)

        body = text[opening_brace + 1:closing_brace]
        blocks.append((match, body))

        position = closing_brace + 1

    return blocks


def parse_multiplicity(
    multiplicity_text: Optional[str],
) -> tuple[int, Optional[int]]:
    if not multiplicity_text:
        return 1, 1

    value = multiplicity_text.strip()

    if value == "*":
        return 0, None

    if ".." in value:
        lower_text, upper_text = value.split("..", 1)

        lower = int(lower_text.strip())
        upper = (
            None
            if upper_text.strip() == "*"
            else int(upper_text.strip())
        )

        return lower, upper

    number = int(value)
    return number, number


def parse_user_model(text: str) -> dict[str, TypeDefinition]:
    """
    Parse part def and port def declarations from a user-defined model.

    Only attributes and features declared directly inside each definition
    are parsed. Declarations inside nested blocks are ignored.
    """

    text = remove_comments(text)

    definition_pattern = re.compile(
        r"\b(?P<kind>part|port)\s+def\s+"
        r"(?P<name>[A-Za-z_]\w*)\s*\{",
        re.MULTILINE,
    )

    definitions: dict[str, TypeDefinition] = {}

    for match, body in extract_top_level_blocks(text, definition_pattern):
        type_name = match.group("name")
        type_kind = match.group("kind")

        definition = TypeDefinition(
            name=type_name,
            kind=type_kind,
        )

        # Remove nested block contents so only direct members of the
        # current definition are parsed.
        direct_body = remove_nested_blocks(body)

        attribute_pattern = re.compile(
            r"\battribute\s+"
            r"(?P<name>[A-Za-z_]\w*)\s*:\s*"
            r"(?P<type>[A-Za-z_]\w*(?:::\w+)*)"
            r"(?:\s*=\s*.*?)?\s*;",
            re.MULTILINE,
        )

        for attribute_match in attribute_pattern.finditer(direct_body):
            attribute = AttributeDefinition(
                name=attribute_match.group("name"),
                type_name=attribute_match.group("type").split("::")[-1],
            )

            definition.attributes[attribute.name] = attribute

        feature_pattern = re.compile(
            r"\b(?P<kind>part|port)\s+"
            r"(?P<name>[A-Za-z_]\w*)"
            r"(?:\s*\[\s*(?P<multiplicity>[^\]]+)\s*\])?"
            r"\s*:\s*"
            r"(?P<type>[A-Za-z_]\w*(?:::\w+)*)"
            r"(?:\s*=\s*.*?)?\s*;",
            re.MULTILINE,
        )

        for feature_match in feature_pattern.finditer(direct_body):
            lower, upper = parse_multiplicity(
                feature_match.group("multiplicity")
            )

            feature = FeatureDefinition(
                name=feature_match.group("name"),
                type_name=feature_match.group("type").split("::")[-1],
                feature_kind=feature_match.group("kind"),
                lower=lower,
                upper=upper,
            )

            definition.features[feature.name] = feature

        definitions[type_name] = definition

    return definitions


def parse_value_assignments(body: str) -> dict[str, str]:
    """
    Parse only assignments belonging directly to the current instance level.

    Nested part and port bodies are excluded.
    """
    direct_body = remove_nested_blocks(body)

    patterns = [
        re.compile(
            r"\battribute\s+redefines\s+"
            r"(?P<name>[A-Za-z_]\w*)\s*=\s*"
            r"(?P<value>.*?);",
            re.MULTILINE,
        ),
        re.compile(
            r":>>\s*(?P<name>[A-Za-z_]\w*)\s*=\s*"
            r"(?P<value>.*?);",
            re.MULTILINE,
        ),
    ]

    assignments: dict[str, str] = {}

    for pattern in patterns:
        for match in pattern.finditer(direct_body):
            assignments[match.group("name")] = (
                match.group("value").strip()
            )

    return assignments

def remove_nested_blocks(text: str) -> str:
    """
    Replace the content of nested {...} blocks with spaces.

    This preserves only declarations and assignments at the current level.
    """
    result = list(text)
    depth = 0
    in_string = False
    escaped = False

    for index, character in enumerate(text):
        if escaped:
            escaped = False

            if depth > 0:
                result[index] = " "

            continue

        if character == "\\" and in_string:
            escaped = True

            if depth > 0:
                result[index] = " "

            continue

        if character == '"':
            in_string = not in_string

            if depth > 0:
                result[index] = " "

            continue

        if in_string:
            if depth > 0:
                result[index] = " "

            continue

        if character == "{":
            depth += 1
            result[index] = " "
            continue

        if character == "}":
            result[index] = " "
            depth -= 1
            continue

        if depth > 0:
            result[index] = " "

    return "".join(result)

def parse_feature_instances(body: str) -> list[FeatureInstance]:
    """
    Parse nested part and port usages.

    Supported forms:

        part battery {
            ...
        }

        part battery : Battery {
            ...
        }

        port powerOutput {
            ...
        }
    """

    feature_pattern = re.compile(
        r"\b(?P<kind>part|port)\s+"
        r"(?:redefines\s+)?"
        r"(?P<name>[A-Za-z_]\w*)"
        r"(?:\s*:\s*(?P<type>[A-Za-z_]\w*(?:::\w+)*))?"
        r"\s*\{",
        re.MULTILINE,
    )

    instances: list[FeatureInstance] = []

    for match, nested_body in extract_top_level_blocks(body, feature_pattern):
        declared_type = match.group("type")

        instance = FeatureInstance(
            name=match.group("name"),
            kind=match.group("kind"),
            declared_type=(
                declared_type.split("::")[-1]
                if declared_type
                else None
            ),
            values=parse_value_assignments(nested_body),
            children=parse_feature_instances(nested_body),
        )

        instances.append(instance)

    return instances


def parse_model_instances(text: str) -> list[FeatureInstance]:
    """
    Parse top-level typed part usages such as:

        part myVehicle : ElectricVehicle {
            ...
        }
    """

    text = remove_comments(text)

    instance_pattern = re.compile(
        r"\bpart\s+"
        r"(?P<name>[A-Za-z_]\w*)\s*:\s*"
        r"(?P<type>[A-Za-z_]\w*(?:::\w+)*)\s*\{",
        re.MULTILINE,
    )

    instances: list[FeatureInstance] = []

    for match, body in extract_top_level_blocks(text, instance_pattern):
        instance = FeatureInstance(
            name=match.group("name"),
            kind="part",
            declared_type=match.group("type").split("::")[-1],
            values=parse_value_assignments(body),
            children=parse_feature_instances(body),
        )

        instances.append(instance)

    return instances


def validate_primitive_value(
    value: str,
    expected_type: str,
) -> bool:
    value = value.strip()

    if expected_type == "Boolean":
        return value.lower() in {"true", "false"}

    if expected_type in {"Integer", "Natural"}:
        if not re.fullmatch(r"[+-]?\d+", value):
            return False

        if expected_type == "Natural":
            return int(value) >= 0

        return True

    if expected_type in {"Real", "Rational"}:
        return bool(
            re.fullmatch(
                r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
                r"(?:[eE][+-]?\d+)?",
                value,
            )
        )

    if expected_type == "String":
        return (
            len(value) >= 2
            and value.startswith('"')
            and value.endswith('"')
        )

    # User-defined datatypes or expressions are not evaluated here.
    return True


def validate_instance(
    instance: FeatureInstance,
    expected_type_name: str,
    definitions: dict[str, TypeDefinition],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    definition = definitions.get(expected_type_name)

    if definition is None:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                path=path,
                message=(
                    f"Unknown user-defined type '{expected_type_name}'."
                ),
            )
        )
        return

    if (
        instance.declared_type is not None
        and instance.declared_type != expected_type_name
    ):
        issues.append(
            ValidationIssue(
                severity="ERROR",
                path=path,
                message=(
                    f"Instance declares type '{instance.declared_type}', "
                    f"but '{expected_type_name}' is required."
                ),
            )
        )

    for attribute_name, value in instance.values.items():
        attribute_definition = definition.attributes.get(attribute_name)

        if attribute_definition is None:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    path=f"{path}.{attribute_name}",
                    message=(
                        f"Attribute '{attribute_name}' is not defined "
                        f"by type '{expected_type_name}'."
                    ),
                )
            )
            continue

        if not validate_primitive_value(
            value,
            attribute_definition.type_name,
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    path=f"{path}.{attribute_name}",
                    message=(
                        f"Value '{value}' is not valid for type "
                        f"'{attribute_definition.type_name}'."
                    ),
                )
            )

    child_groups: dict[str, list[FeatureInstance]] = {}

    for child in instance.children:
        child_groups.setdefault(child.name, []).append(child)

    for child_name, children in child_groups.items():
        feature_definition = definition.features.get(child_name)

        if feature_definition is None:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    path=f"{path}.{child_name}",
                    message=(
                        f"Feature '{child_name}' is not defined "
                        f"by type '{expected_type_name}'."
                    ),
                )
            )
            continue

        if any(
            child.kind != feature_definition.feature_kind
            for child in children
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    path=f"{path}.{child_name}",
                    message=(
                        f"Feature '{child_name}' must be declared as "
                        f"'{feature_definition.feature_kind}', not "
                        f"'{children[0].kind}'."
                    ),
                )
            )

        count = len(children)

        if count < feature_definition.lower:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    path=f"{path}.{child_name}",
                    message=(
                        f"Feature '{child_name}' requires at least "
                        f"{feature_definition.lower} occurrence(s), "
                        f"but {count} were provided."
                    ),
                )
            )

        if (
            feature_definition.upper is not None
            and count > feature_definition.upper
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    path=f"{path}.{child_name}",
                    message=(
                        f"Feature '{child_name}' allows at most "
                        f"{feature_definition.upper} occurrence(s), "
                        f"but {count} were provided."
                    ),
                )
            )

        for index, child in enumerate(children):
            child_path = f"{path}.{child_name}"

            if len(children) > 1:
                child_path += f"[{index}]"

            validate_instance(
                instance=child,
                expected_type_name=feature_definition.type_name,
                definitions=definitions,
                path=child_path,
                issues=issues,
            )

    # Missing features are reported only when their lower multiplicity is > 0.
    for feature_name, feature_definition in definition.features.items():
        count = len(child_groups.get(feature_name, []))

        if count < feature_definition.lower:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    path=f"{path}.{feature_name}",
                    message=(
                        f"Required feature '{feature_name}' is missing. "
                        f"Expected at least "
                        f"{feature_definition.lower} occurrence(s)."
                    ),
                )
            )


def validate_files(
    definition_file: Path,
    instance_file: Path,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "valid": False,
        "definition_file": str(definition_file),
        "instance_file": str(instance_file),
        "definitions": [],
        "instances": [],
        "errors": [],
        "warnings": [],
    }

    if not definition_file.is_file():
        report["errors"].append(
            {
                "severity": "ERROR",
                "path": str(definition_file),
                "message": "User-defined model file does not exist.",
            }
        )
        return report

    if not instance_file.is_file():
        report["errors"].append(
            {
                "severity": "ERROR",
                "path": str(instance_file),
                "message": "Model-instance file does not exist.",
            }
        )
        return report

    try:
        definition_text = definition_file.read_text(encoding="utf-8")
        instance_text = instance_file.read_text(encoding="utf-8")

        definitions = parse_user_model(definition_text)
        instances = parse_model_instances(instance_text)

    except (OSError, ValueError) as exception:
        report["errors"].append(
            {
                "severity": "ERROR",
                "path": "",
                "message": str(exception),
            }
        )
        return report

    report["definitions"] = sorted(definitions.keys())
    report["instances"] = [instance.name for instance in instances]

    issues: list[ValidationIssue] = []

    if not definitions:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                path=str(definition_file),
                message=(
                    "No 'part def' or 'port def' declarations were found."
                ),
            )
        )

    if not instances:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                path=str(instance_file),
                message="No typed top-level part usages were found.",
            )
        )

    for instance in instances:
        if instance.declared_type is None:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    path=instance.name,
                    message="Top-level instance has no declared type.",
                )
            )
            continue

        validate_instance(
            instance=instance,
            expected_type_name=instance.declared_type,
            definitions=definitions,
            path=instance.name,
            issues=issues,
        )

    report["errors"] = [
        issue.to_dict()
        for issue in issues
        if issue.severity == "ERROR"
    ]

    report["warnings"] = [
        issue.to_dict()
        for issue in issues
        if issue.severity == "WARNING"
    ]

    report["valid"] = len(report["errors"]) == 0

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a SysML v2 model instance against a "
            "user-defined structural model."
        )
    )

    parser.add_argument(
        "definition_model",
        type=Path,
        help="SysML file containing part def and port def declarations.",
    )

    parser.add_argument(
        "instance_model",
        type=Path,
        help="SysML file containing typed part usages.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report output file.",
    )

    arguments = parser.parse_args()

    report = validate_files(
        definition_file=arguments.definition_model,
        instance_file=arguments.instance_model,
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if arguments.output:
        arguments.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())