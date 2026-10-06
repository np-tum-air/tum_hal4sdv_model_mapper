#!/usr/bin/env python3

"""
metamodel_merge_eval.py

Semantic evaluation of metamodel merging.

Supported scenarios:
    Ecore + Ecore       -> Ecore
    Ecore + SysML v2    -> SysML v2
    SysML v2 + SysML v2 -> SysML v2

The expected result is the semantic UNION of the two source
metamodels. Duplicate elements are counted only once.

Evaluated aspects:
    1. Classes / part definitions
    2. Attributes
    3. Relationships / contained parts
    4. Inheritance relationships

Usage:

    python metamodel_merge_eval.py \
        source1.ecore source2.ecore merged.ecore

    python metamodel_merge_eval.py \
        source.ecore source.sysml merged.sysml

    python metamodel_merge_eval.py \
        source1.sysml source2.sysml merged.sysml

Optional:

    python metamodel_merge_eval.py \
        source1.ecore source2.ecore merged.ecore \
        --json results.json
"""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


# ============================================================
# Semantic aliases
# ============================================================

# Add project-specific mappings when the two modeling
# technologies use different names for the same concept.

NAME_ALIASES = {
    "fov": "fieldOfView",
}


def canonical(name):

    if name is None:
        return None

    name = name.strip()

    return NAME_ALIASES.get(
        name,
        name
    )


# ============================================================
# Utility functions
# ============================================================

def local_name(tag):

    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def normalize_type(value):

    if value is None:
        return None

    value = value.strip()

    # Ecore types may look like:
    #
    # #//CameraSensor
    # ecore:EString
    # http://...#//Sensor

    if "#//" in value:
        value = value.split("#//")[-1]

    if ":" in value:
        value = value.split(":")[-1]

    return canonical(value)


def strip_comments(text):

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


# ============================================================
# Semantic representation
# ============================================================

def empty_model():

    return {
        "classes": set(),
        "attributes": set(),
        "relationships": set(),
        "inheritance": set()
    }


# ============================================================
# ECORE PARSER
# ============================================================

def parse_ecore(path):

    model = empty_model()

    tree = ET.parse(path)

    root = tree.getroot()

    # --------------------------------------------------------
    # Find EClasses
    # --------------------------------------------------------

    for element in root.iter():

        xsi_type = None

        for key, value in element.attrib.items():

            if local_name(key) == "type":
                xsi_type = value

        # EClass normally:
        #
        # <eClassifiers xsi:type="ecore:EClass"
        #               name="Sensor">

        if (
            local_name(element.tag) == "eClassifiers"
            and xsi_type
            and xsi_type.endswith("EClass")
        ):

            class_name = canonical(
                element.attrib.get("name")
            )

            if not class_name:
                continue

            model["classes"].add(
                class_name
            )

            # ------------------------------------------------
            # Inheritance
            # ------------------------------------------------

            super_types = element.attrib.get(
                "eSuperTypes"
            )

            if super_types:

                for super_type in super_types.split():

                    parent = normalize_type(
                        super_type
                    )

                    if parent:

                        model["inheritance"].add(
                            (
                                class_name,
                                parent
                            )
                        )

            # ------------------------------------------------
            # Structural features
            # ------------------------------------------------

            for feature in element:

                if local_name(feature.tag) != "eStructuralFeatures":
                    continue

                feature_type = None

                for key, value in feature.attrib.items():

                    if local_name(key) == "type":
                        feature_type = value

                feature_name = canonical(
                    feature.attrib.get("name")
                )

                if not feature_name:
                    continue

                # --------------------------------------------
                # EAttribute
                # --------------------------------------------

                if (
                    feature_type
                    and feature_type.endswith("EAttribute")
                ):

                    data_type = normalize_type(
                        feature.attrib.get("eType")
                    )

                    model["attributes"].add(
                        (
                            class_name,
                            feature_name,
                            data_type
                        )
                    )

                # --------------------------------------------
                # EReference
                # --------------------------------------------

                elif (
                    feature_type
                    and feature_type.endswith("EReference")
                ):

                    target = normalize_type(
                        feature.attrib.get("eType")
                    )

                    model["relationships"].add(
                        (
                            class_name,
                            feature_name,
                            target
                        )
                    )

    return model


# ============================================================
# SYSML v2 PARSER
# ============================================================

def extract_balanced_block(text, start_brace):

    depth = 0

    for i in range(
        start_brace,
        len(text)
    ):

        if text[i] == "{":
            depth += 1

        elif text[i] == "}":

            depth -= 1

            if depth == 0:

                return text[
                    start_brace + 1:i
                ]

    return ""


def parse_sysml(path):

    model = empty_model()

    text = Path(path).read_text(
        encoding="utf-8"
    )

    text = strip_comments(text)

    # --------------------------------------------------------
    # Part definitions
    #
    # Examples:
    #
    # part def Sensor {
    #
    # abstract part def Actuator {
    #
    # part def BrakeActuator
    #     specializes Actuator {
    #
    # --------------------------------------------------------

    part_pattern = re.compile(
        r"(?:abstract\s+)?"
        r"part\s+def\s+"
        r"([A-Za-z_]\w*)"
        r"(?:\s+specializes\s+"
        r"([A-Za-z_]\w*))?"
        r"\s*\{",
        re.MULTILINE
    )

    matches = list(
        part_pattern.finditer(text)
    )

    for match in matches:

        class_name = canonical(
            match.group(1)
        )

        parent = canonical(
            match.group(2)
        )

        model["classes"].add(
            class_name
        )

        # ----------------------------------------------------
        # Inheritance
        # ----------------------------------------------------

        if parent:

            model["inheritance"].add(
                (
                    class_name,
                    parent
                )
            )

        # ----------------------------------------------------
        # Extract body of this part definition
        # ----------------------------------------------------

        opening_brace = (
            match.end() - 1
        )

        body = extract_balanced_block(
            text,
            opening_brace
        )

        # ----------------------------------------------------
        # Attributes
        #
        # attribute resolution : String;
        #
        # ----------------------------------------------------

        attribute_pattern = re.compile(
            r"\battribute\s+"
            r"([A-Za-z_]\w*)"
            r"\s*:\s*"
            r"([A-Za-z_]\w*)"
            r"\s*;"
        )

        for attr_match in attribute_pattern.finditer(body):

            attribute_name = canonical(
                attr_match.group(1)
            )

            attribute_type = normalize_type(
                attr_match.group(2)
            )

            model["attributes"].add(
                (
                    class_name,
                    attribute_name,
                    attribute_type
                )
            )

        # ----------------------------------------------------
        # Part relationships
        #
        # part camera : CameraSensor;
        #
        # ----------------------------------------------------

        relationship_pattern = re.compile(
            r"\bpart\s+"
            r"(?!def\b)"
            r"([A-Za-z_]\w*)"
            r"\s*:\s*"
            r"([A-Za-z_]\w*)"
            r"\s*;"
        )

        for rel_match in relationship_pattern.finditer(body):

            relationship_name = canonical(
                rel_match.group(1)
            )

            target_type = normalize_type(
                rel_match.group(2)
            )

            model["relationships"].add(
                (
                    class_name,
                    relationship_name,
                    target_type
                )
            )

    return model


# ============================================================
# Automatic format detection
# ============================================================

def detect_format(path):

    extension = (
        Path(path)
        .suffix
        .lower()
    )

    if extension in [
        ".ecore",
        ".xml",
        ".xmi"
    ]:
        return "ecore"

    if extension in [
        ".sysml",
        ".sysml2"
    ]:
        return "sysml"

    raise ValueError(
        f"Cannot detect model format: {path}"
    )


def parse_model(path):

    model_format = detect_format(
        path
    )

    if model_format == "ecore":

        return parse_ecore(path)

    if model_format == "sysml":

        return parse_sysml(path)

    raise ValueError(
        f"Unsupported format: {path}"
    )


# ============================================================
# Semantic union
# ============================================================

def semantic_union(model1, model2):

    union = empty_model()

    for category in union:

        union[category] = (
            model1[category]
            | model2[category]
        )

    return union


# ============================================================
# Evaluation
# ============================================================

def evaluate_category(expected, generated):

    matched = (
        expected
        & generated
    )

    missing = (
        expected
        - generated
    )

    additional = (
        generated
        - expected
    )

    total = len(expected)

    matched_count = len(matched)

    if total == 0:

        percentage = 100.0

    else:

        percentage = (
            100.0
            * matched_count
            / total
        )

    return {
        "expected": total,
        "generated": len(generated),
        "matched": matched_count,
        "percentage": percentage,
        "missing": sorted(
            list(missing),
            key=str
        ),
        "additional": sorted(
            list(additional),
            key=str
        )
    }


def evaluate(source1, source2, merged):

    expected = semantic_union(
        source1,
        source2
    )

    results = {}

    for category in [
        "classes",
        "attributes",
        "relationships",
        "inheritance"
    ]:

        results[category] = evaluate_category(
            expected[category],
            merged[category]
        )

    # --------------------------------------------------------
    # Overall semantic preservation
    # --------------------------------------------------------

    total_expected = sum(
        results[x]["expected"]
        for x in results
    )

    total_matched = sum(
        results[x]["matched"]
        for x in results
    )

    if total_expected == 0:

        overall = 100.0

    else:

        overall = (
            100.0
            * total_matched
            / total_expected
        )

    results["overall"] = {
        "expected": total_expected,
        "matched": total_matched,
        "percentage": overall
    }

    return expected, results


# ============================================================
# Printing
# ============================================================

def format_element(element):

    if isinstance(element, tuple):

        return " :: ".join(
            str(x)
            for x in element
            if x is not None
        )

    return str(element)


def print_model(title, model):

    print()
    print(title)
    print("=" * 72)

    for category in [
        "classes",
        "attributes",
        "relationships",
        "inheritance"
    ]:

        print()
        print(
            category.upper()
        )

        print("-" * 72)

        if not model[category]:

            print("(none)")

        else:

            for element in sorted(
                model[category],
                key=str
            ):

                print(
                    format_element(element)
                )


def print_results(results):

    print()
    print("METAMODEL MERGING SEMANTIC EVALUATION")
    print("=" * 78)

    print(
        f"{'Aspect':<22}"
        f"{'Expected union':>16}"
        f"{'Generated':>12}"
        f"{'Matched':>12}"
        f"{'Score':>12}"
    )

    print("-" * 78)

    labels = {
        "classes": "Classes",
        "attributes": "Attributes",
        "relationships": "Relationships",
        "inheritance": "Inheritance"
    }

    for category in [
        "classes",
        "attributes",
        "relationships",
        "inheritance"
    ]:

        r = results[category]

        print(
            f"{labels[category]:<22}"
            f"{r['expected']:>16}"
            f"{r['generated']:>12}"
            f"{str(r['matched']) + '/' + str(r['expected']):>12}"
            f"{r['percentage']:>11.1f}%"
        )

    print("-" * 78)

    overall = results["overall"]

    print(
        f"{'Overall semantic match':<50}"
        f"{str(overall['matched']) + '/' + str(overall['expected']):>16}"
        f"{overall['percentage']:>11.1f}%"
    )


def print_missing(results):

    print()
    print("MISSING ELEMENTS")
    print("=" * 72)

    any_missing = False

    for category in [
        "classes",
        "attributes",
        "relationships",
        "inheritance"
    ]:

        missing = results[
            category
        ]["missing"]

        if missing:

            any_missing = True

            print()
            print(
                category.upper()
            )

            for element in missing:

                print(
                    "  - "
                    + format_element(element)
                )

    if not any_missing:

        print(
            "No semantic elements are missing."
        )


def print_additional(results):

    print()
    print("ADDITIONAL GENERATED ELEMENTS")
    print("=" * 72)

    any_additional = False

    for category in [
        "classes",
        "attributes",
        "relationships",
        "inheritance"
    ]:

        additional = results[
            category
        ]["additional"]

        if additional:

            any_additional = True

            print()
            print(
                category.upper()
            )

            for element in additional:

                print(
                    "  + "
                    + format_element(element)
                )

    if not any_additional:

        print(
            "No additional semantic elements were generated."
        )


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate semantic preservation "
            "during metamodel merging."
        )
    )

    parser.add_argument(
        "source1",
        help="First source metamodel"
    )

    parser.add_argument(
        "source2",
        help="Second source metamodel"
    )

    parser.add_argument(
        "merged",
        help="Generated merged metamodel"
    )

    parser.add_argument(
        "--json",
        dest="json_path",
        help="Optional JSON output file"
    )

    parser.add_argument(
        "--details",
        action="store_true",
        help="Print extracted semantic elements"
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Check files
    # --------------------------------------------------------

    for path in [
        args.source1,
        args.source2,
        args.merged
    ]:

        if not Path(path).exists():

            print(
                f"ERROR: File not found: {path}"
            )

            return

    # --------------------------------------------------------
    # Parse models
    # --------------------------------------------------------

    try:

        source1 = parse_model(
            args.source1
        )

        source2 = parse_model(
            args.source2
        )

        merged = parse_model(
            args.merged
        )

    except Exception as error:

        print(
            f"ERROR parsing models: {error}"
        )

        return

    # --------------------------------------------------------
    # Evaluate
    # --------------------------------------------------------

    expected, results = evaluate(
        source1,
        source2,
        merged
    )

    print_results(
        results
    )

    print_missing(
        results
    )

    print_additional(
        results
    )

    # --------------------------------------------------------
    # Optional details
    # --------------------------------------------------------

    if args.details:

        print_model(
            "SOURCE 1",
            source1
        )

        print_model(
            "SOURCE 2",
            source2
        )

        print_model(
            "EXPECTED SEMANTIC UNION",
            expected
        )

        print_model(
            "GENERATED MERGED METAMODEL",
            merged
        )

    # --------------------------------------------------------
    # Optional JSON
    # --------------------------------------------------------

    if args.json_path:

        Path(
            args.json_path
        ).write_text(
            json.dumps(
                results,
                indent=2
            ),
            encoding="utf-8"
        )

        print()
        print(
            f"Results written to: "
            f"{args.json_path}"
        )


if __name__ == "__main__":
    main()