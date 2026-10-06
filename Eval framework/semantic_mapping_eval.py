#!/usr/bin/env python3

"""
semantic_mapping_eval.py

Evaluates semantic mapping between an XMI model instance and
a SysML v2 textual model instance.

The evaluation considers:
1. Component/model instances
2. Attributes
3. Attribute values

Example:
    python semantic_mapping_eval.py vehicle_control.xmi vehicle_control.sysml
"""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

XSI = "http://www.w3.org/2001/XMLSchema-instance"

# Semantic aliases between Ecore/XMI and SysML representations.
# Extend this dictionary if additional equivalent names are used.
ATTRIBUTE_ALIASES = {
    "fov": "fieldOfView",
}

# XMI infrastructure attributes that should not be counted
# as model attributes.
XMI_IGNORED_ATTRIBUTES = {
    f"{{{XSI}}}type",
    "{http://www.omg.org/XMI}version",
}


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def canonical_attribute(name):
    """
    Convert semantically equivalent attribute names to
    one common representation.
    """
    return ATTRIBUTE_ALIASES.get(name, name)


def normalize_value(value):
    """
    Normalize values so that harmless representation differences
    do not affect semantic matching.

    Examples:
        "120.0" -> "120"
        120.0   -> "120"
        "0.20"  -> "0.2"
    """

    value = str(value).strip()

    # Remove quotation marks
    value = value.strip('"').strip("'")

    # Normalize numeric values
    try:
        number = float(value)

        if number.is_integer():
            return str(int(number))

        return format(number, ".15g")

    except ValueError:
        return value


def local_name(tag):
    """
    Remove an XML namespace from a tag or attribute name.
    """

    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def type_name(value):
    """
    Convert:
        hw:CameraSensor
    into:
        CameraSensor
    """

    return value.split(":")[-1]


# ------------------------------------------------------------
# XMI parser
# ------------------------------------------------------------

def parse_xmi(path):

    tree = ET.parse(path)
    root = tree.getroot()

    components = []
    attributes = []
    values = []

    # --------------------------------------------------------
    # Root model instance
    # --------------------------------------------------------

    root_type = local_name(root.tag)
    root_name = root.attrib.get("name")

    components.append({
        "name": root_name,
        "type": root_type,
        "kind": "root"
    })

    # --------------------------------------------------------
    # Child component instances
    # --------------------------------------------------------

    for elem in root.iter():

        if elem is root:
            continue

        xsi_type = elem.attrib.get(
            f"{{{XSI}}}type"
        )

        if xsi_type:

            components.append({
                "name": elem.attrib.get("name"),
                "type": type_name(xsi_type),
                "kind": local_name(elem.tag)
            })

        # ----------------------------------------------------
        # Attributes and values
        # ----------------------------------------------------

        for key, value in elem.attrib.items():

            if key in XMI_IGNORED_ATTRIBUTES:
                continue

            attr = local_name(key)

            # "name" identifies the model instance.
            # It is therefore not counted as a property.
            if attr == "name":
                continue

            attr = canonical_attribute(attr)

            attributes.append(attr)

            values.append(
                (
                    attr,
                    normalize_value(value)
                )
            )

    return {
        "components": components,
        "attributes": attributes,
        "values": values
    }


# ------------------------------------------------------------
# SysML parser
# ------------------------------------------------------------

def strip_sysml_comments(text):
    """
    Remove // and /* */ comments.
    """

    text = re.sub(
        r"/\*.*?\*/",
        "",
        text,
        flags=re.S
    )

    text = re.sub(
        r"//.*?$",
        "",
        text,
        flags=re.M
    )

    return text


def parse_sysml(path):

    text = Path(path).read_text(
        encoding="utf-8"
    )

    text = strip_sysml_comments(text)

    components = []
    attributes = []
    values = []

    # --------------------------------------------------------
    # Typed top-level part usage
    #
    # Example:
    #
    # part vehicleControlPlatform : HardwarePlatform {
    #
    # --------------------------------------------------------

    typed_part_pattern = re.compile(
        r"\bpart\s+"
        r"(?!def\b|redefines\b)"
        r"([A-Za-z_]\w*)"
        r"\s*:\s*"
        r"([A-Za-z_]\w*)"
        r"\s*\{"
    )

    for match in typed_part_pattern.finditer(text):

        components.append({
            "name": match.group(1),
            "type": match.group(2),
            "kind": "root"
        })

    # --------------------------------------------------------
    # Redefined component instances
    #
    # Example:
    #
    # part redefines camera {
    #
    # --------------------------------------------------------

    redefined_part_pattern = re.compile(
        r"\bpart\s+redefines\s+"
        r"([A-Za-z_]\w*)"
        r"\s*\{"
    )

    for match in redefined_part_pattern.finditer(text):

        components.append({
            "name": match.group(1),
            "type": None,
            "kind": "redefined"
        })

    # --------------------------------------------------------
    # Attribute-value assignments
    #
    # Example:
    #
    # attribute redefines fieldOfView = 120.0;
    #
    # --------------------------------------------------------

    attribute_pattern = re.compile(
        r"\battribute\s+redefines\s+"
        r"([A-Za-z_]\w*)"
        r"\s*=\s*"
        r"([^;]+);"
    )

    for match in attribute_pattern.finditer(text):

        attr = canonical_attribute(
            match.group(1)
        )

        value = normalize_value(
            match.group(2)
        )

        attributes.append(attr)

        values.append(
            (
                attr,
                value
            )
        )

    return {
        "components": components,
        "attributes": attributes,
        "values": values
    }


# ------------------------------------------------------------
# Evaluation
# ------------------------------------------------------------

def component_names(model):

    return [
        component["name"]
        for component in model["components"]
        if component["name"]
    ]


def multiset_score(reference, candidate):
    """
    Calculate semantic preservation relative to the reference.

    Duplicate attributes are preserved using Counter.

    Example:

        reference:
            resolution
            fieldOfView
            resolution
            fieldOfView

        candidate:
            resolution
            fieldOfView
            resolution

        -> 3 / 4
    """

    ref = Counter(reference)
    cand = Counter(candidate)

    matched = sum(
        (ref & cand).values()
    )

    total = sum(
        ref.values()
    )

    if total == 0:
        percentage = 100.0
    else:
        percentage = (
            100.0 * matched / total
        )

    return matched, total, percentage


def compare(xmi, sysml):

    xmi_components = component_names(xmi)
    sysml_components = component_names(sysml)

    # --------------------------------------------------------
    # Component matching
    # --------------------------------------------------------

    component_match = multiset_score(
        xmi_components,
        sysml_components
    )

    # --------------------------------------------------------
    # Attribute matching
    # --------------------------------------------------------

    attribute_match = multiset_score(
        xmi["attributes"],
        sysml["attributes"]
    )

    # --------------------------------------------------------
    # Attribute-value matching
    # --------------------------------------------------------

    value_match = multiset_score(
        xmi["values"],
        sysml["values"]
    )

    # --------------------------------------------------------
    # Overall semantic matching
    # --------------------------------------------------------

    matched = (
        component_match[0]
        + attribute_match[0]
        + value_match[0]
    )

    total = (
        component_match[1]
        + attribute_match[1]
        + value_match[1]
    )

    if total == 0:
        overall_percentage = 100.0
    else:
        overall_percentage = (
            100.0 * matched / total
        )

    return {

        "counts": {

            "xmi": {
                "components": len(xmi_components),
                "attributes": len(xmi["attributes"]),
                "values": len(xmi["values"])
            },

            "sysml": {
                "components": len(sysml_components),
                "attributes": len(sysml["attributes"]),
                "values": len(sysml["values"])
            }
        },

        "matching": {

            "components": {
                "matched": component_match[0],
                "reference": component_match[1],
                "percentage": component_match[2]
            },

            "attributes": {
                "matched": attribute_match[0],
                "reference": attribute_match[1],
                "percentage": attribute_match[2]
            },

            "values": {
                "matched": value_match[0],
                "reference": value_match[1],
                "percentage": value_match[2]
            },

            "overall": {
                "matched": matched,
                "reference": total,
                "percentage": overall_percentage
            }
        }
    }


# ------------------------------------------------------------
# Output
# ------------------------------------------------------------

def print_components(title, model):

    print()
    print(title)
    print("-" * 60)

    for component in model["components"]:

        name = component["name"]
        component_type = component["type"]

        if component_type:
            print(
                f"{name} : {component_type}"
            )
        else:
            print(name)


def print_attributes(title, model):

    print()
    print(title)
    print("-" * 60)

    for attr, value in model["values"]:

        print(
            f"{attr} = {value}"
        )


def print_results(xmi, sysml, result):

    print()
    print("SEMANTIC MAPPING EVALUATION")
    print("=" * 72)

    print(
        f"{'Aspect':<24}"
        f"{'XMI':>8}"
        f"{'SysML':>10}"
        f"{'Matched':>12}"
        f"{'Score':>12}"
    )

    print("-" * 72)

    # --------------------------------------------------------
    # Components
    # --------------------------------------------------------

    match = result["matching"]["components"]

    print(
        f"{'Components / instances':<24}"
        f"{result['counts']['xmi']['components']:>8}"
        f"{result['counts']['sysml']['components']:>10}"
        f"{str(match['matched']) + '/' + str(match['reference']):>12}"
        f"{match['percentage']:>11.1f}%"
    )

    # --------------------------------------------------------
    # Attributes
    # --------------------------------------------------------

    match = result["matching"]["attributes"]

    print(
        f"{'Attributes':<24}"
        f"{result['counts']['xmi']['attributes']:>8}"
        f"{result['counts']['sysml']['attributes']:>10}"
        f"{str(match['matched']) + '/' + str(match['reference']):>12}"
        f"{match['percentage']:>11.1f}%"
    )

    # --------------------------------------------------------
    # Values
    # --------------------------------------------------------

    match = result["matching"]["values"]

    print(
        f"{'Attribute values':<24}"
        f"{result['counts']['xmi']['values']:>8}"
        f"{result['counts']['sysml']['values']:>10}"
        f"{str(match['matched']) + '/' + str(match['reference']):>12}"
        f"{match['percentage']:>11.1f}%"
    )

    print("-" * 72)

    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------

    overall = result["matching"]["overall"]

    print(
        f"{'Overall semantic mapping':<44}"
        f"{str(overall['matched']) + '/' + str(overall['reference']):>16}"
        f"{overall['percentage']:>11.1f}%"
    )

    # --------------------------------------------------------
    # Detailed information
    # --------------------------------------------------------

    print_components(
        "XMI COMPONENTS",
        xmi
    )

    print_components(
        "SYSML COMPONENTS",
        sysml
    )

    print_attributes(
        "XMI ATTRIBUTE VALUES",
        xmi
    )

    print_attributes(
        "SYSML ATTRIBUTE VALUES",
        sysml
    )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate semantic mapping between "
            "XMI and SysML v2 model instances."
        )
    )

    parser.add_argument(
        "xmi",
        help="Reference XMI model instance"
    )

    parser.add_argument(
        "sysml",
        help="SysML v2 model instance"
    )

    parser.add_argument(
        "--json",
        dest="json_path",
        help="Optional JSON output file"
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Check files
    # --------------------------------------------------------

    if not Path(args.xmi).exists():

        print(
            f"ERROR: XMI file not found: {args.xmi}"
        )

        return

    if not Path(args.sysml).exists():

        print(
            f"ERROR: SysML file not found: {args.sysml}"
        )

        return

    # --------------------------------------------------------
    # Parse models
    # --------------------------------------------------------

    try:

        xmi = parse_xmi(
            args.xmi
        )

    except Exception as error:

        print(
            f"ERROR parsing XMI: {error}"
        )

        return

    try:

        sysml = parse_sysml(
            args.sysml
        )

    except Exception as error:

        print(
            f"ERROR parsing SysML: {error}"
        )

        return

    # --------------------------------------------------------
    # Compare
    # --------------------------------------------------------

    result = compare(
        xmi,
        sysml
    )

    # --------------------------------------------------------
    # Print results
    # --------------------------------------------------------

    print_results(
        xmi,
        sysml,
        result
    )

    # --------------------------------------------------------
    # Optional JSON
    # --------------------------------------------------------

    if args.json_path:

        Path(
            args.json_path
        ).write_text(
            json.dumps(
                result,
                indent=2
            ),
            encoding="utf-8"
        )

        print()
        print(
            f"JSON results written to: "
            f"{args.json_path}"
        )


if __name__ == "__main__":
    main()