#!/usr/bin/env python3

"""
Validate an XMI model instance against an Ecore metamodel.

Usage:
    python validate_xmi.py metamodel.ecore instance.xmi

Exit codes:
    0 - model is valid
    1 - validation errors were found
    2 - metamodel or model could not be loaded
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from pyecore.ecore import (
    EAttribute,
    EClass,
    EDataType,
    EEnum,
    EObject,
    EPackage,
    EReference,
    EStructuralFeature,
)
from pyecore.resources import ResourceSet, URI
from pyecore.resources.xmi import XMIResource


@dataclass
class ValidationIssue:
    severity: str
    message: str
    object_path: str
    feature_name: Optional[str] = None

    def __str__(self) -> str:
        feature = f".{self.feature_name}" if self.feature_name else ""
        return (
            f"[{self.severity}] "
            f"{self.object_path}{feature}: {self.message}"
        )


class EcoreInstanceValidator:
    def __init__(self) -> None:
        self.issues: list[ValidationIssue] = []

    def error(
        self,
        obj: EObject,
        message: str,
        feature: Optional[EStructuralFeature] = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity="ERROR",
                message=message,
                object_path=self.object_path(obj),
                feature_name=feature.name if feature is not None else None,
            )
        )

    def warning(
        self,
        obj: EObject,
        message: str,
        feature: Optional[EStructuralFeature] = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity="WARNING",
                message=message,
                object_path=self.object_path(obj),
                feature_name=feature.name if feature is not None else None,
            )
        )

    def validate_resource(self, roots: Iterable[EObject]) -> list[ValidationIssue]:
        visited: set[int] = set()

        for root in roots:
            self.validate_object_recursive(root, visited)

        return self.issues

    def validate_object_recursive(
        self,
        obj: EObject,
        visited: set[int],
    ) -> None:
        object_id = id(obj)

        if object_id in visited:
            return

        visited.add(object_id)
        self.validate_object(obj)

        try:
            children = list(obj.eContents)
        except Exception as exc:
            self.error(obj, f"Cannot retrieve contained objects: {exc}")
            return

        for child in children:
            if not isinstance(child, EObject):
                self.error(
                    obj,
                    f"Containment contains a non-EObject value: {child!r}",
                )
                continue

            self.validate_object_recursive(child, visited)

    def validate_object(self, obj: EObject) -> None:
        eclass = getattr(obj, "eClass", None)

        if not isinstance(eclass, EClass):
            self.error(obj, "Object has no valid EClass.")
            return

        if eclass.abstract:
            self.error(
                obj,
                f"Instance directly uses abstract class '{eclass.name}'.",
            )

        for feature in eclass.eAllStructuralFeatures():
            self.validate_feature(obj, feature)

        self.validate_container(obj)

    def validate_feature(
        self,
        obj: EObject,
        feature: EStructuralFeature,
    ) -> None:
        try:
            value = obj.eGet(feature)
        except Exception as exc:
            self.error(
                obj,
                f"Cannot read feature value: {exc}",
                feature,
            )
            return

        if feature.many:
            self.validate_many_feature(obj, feature, value)
        else:
            self.validate_single_feature(obj, feature, value)

    def validate_single_feature(
        self,
        obj: EObject,
        feature: EStructuralFeature,
        value: Any,
    ) -> None:
        is_missing = value is None

        if isinstance(feature, EAttribute):
            try:
                is_set = obj.eIsSet(feature)
            except Exception:
                is_set = not is_missing

            if feature.lowerBound > 0 and not is_set:
                self.error(
                    obj,
                    f"Required attribute must be set "
                    f"(lowerBound={feature.lowerBound}).",
                    feature,
                )

            if not is_missing:
                self.validate_attribute_type(obj, feature, value)

        elif isinstance(feature, EReference):
            if feature.lowerBound > 0 and is_missing:
                self.error(
                    obj,
                    f"Required reference must be set "
                    f"(lowerBound={feature.lowerBound}).",
                    feature,
                )

            if not is_missing:
                self.validate_reference_value(obj, feature, value)
                self.validate_opposite(obj, feature, value)

    def validate_many_feature(
        self,
        obj: EObject,
        feature: EStructuralFeature,
        value: Any,
    ) -> None:
        if value is None:
            values: list[Any] = []
        else:
            try:
                values = list(value)
            except TypeError:
                self.error(
                    obj,
                    "Multi-valued feature does not contain a collection.",
                    feature,
                )
                return

        value_count = len(values)

        if value_count < feature.lowerBound:
            self.error(
                obj,
                f"Feature contains {value_count} value(s), but at least "
                f"{feature.lowerBound} required.",
                feature,
            )

        if feature.upperBound >= 0 and value_count > feature.upperBound:
            self.error(
                obj,
                f"Feature contains {value_count} value(s), but at most "
                f"{feature.upperBound} allowed.",
                feature,
            )

        if feature.unique:
            self.validate_uniqueness(obj, feature, values)

        for index, item in enumerate(values):
            if item is None:
                self.error(
                    obj,
                    f"Value at index {index} is null.",
                    feature,
                )
                continue

            if isinstance(feature, EAttribute):
                self.validate_attribute_type(
                    obj,
                    feature,
                    item,
                    index=index,
                )

            elif isinstance(feature, EReference):
                self.validate_reference_value(
                    obj,
                    feature,
                    item,
                    index=index,
                )
                self.validate_opposite(
                    obj,
                    feature,
                    item,
                    index=index,
                )

    def validate_attribute_type(
        self,
        obj: EObject,
        feature: EAttribute,
        value: Any,
        index: Optional[int] = None,
    ) -> None:
        expected_type = feature.eType
        location = f" at index {index}" if index is not None else ""

        if isinstance(expected_type, EEnum):
            valid_literals = list(expected_type.eLiterals)

            literal_names = {literal.name for literal in valid_literals}
            literal_values = {
                getattr(literal, "value", None)
                for literal in valid_literals
            }

            value_name = getattr(value, "name", None)
            value_literal = getattr(value, "value", value)

            if (
                value not in valid_literals
                and value_name not in literal_names
                and value_literal not in literal_values
            ):
                self.error(
                    obj,
                    f"Invalid enumeration value{location}: {value!r}. "
                    f"Expected a literal of '{expected_type.name}'.",
                    feature,
                )
            return

        if not isinstance(expected_type, EDataType):
            self.error(
                obj,
                f"Attribute has invalid datatype '{expected_type}'.",
                feature,
            )
            return

        python_type = getattr(expected_type, "eType", None)

        if python_type is None:
            python_type = getattr(expected_type, "python_type", None)

        if python_type is None or python_type is object:
            return

        # In Python bool is a subclass of int. Treat it separately.
        if python_type is int and isinstance(value, bool):
            self.error(
                obj,
                f"Invalid value type{location}: expected int, got bool.",
                feature,
            )
            return

        try:
            type_is_valid = isinstance(value, python_type)
        except TypeError:
            # Some custom EDataTypes do not expose a normal Python class.
            return

        if not type_is_valid:
            expected_name = getattr(
                python_type,
                "__name__",
                str(python_type),
            )

            self.error(
                obj,
                f"Invalid value type{location}: expected "
                f"'{expected_type.name}'/{expected_name}, got "
                f"'{type(value).__name__}'.",
                feature,
            )

        if isinstance(value, float) and (
            math.isnan(value) or math.isinf(value)
        ):
            self.warning(
                obj,
                f"Floating-point value{location} is {value}.",
                feature,
            )

    def validate_reference_value(
        self,
        obj: EObject,
        feature: EReference,
        value: Any,
        index: Optional[int] = None,
    ) -> None:
        location = f" at index {index}" if index is not None else ""

        if not isinstance(value, EObject):
            self.error(
                obj,
                f"Reference value{location} is not an EObject: {value!r}.",
                feature,
            )
            return

        if self.is_proxy(value):
            self.error(
                obj,
                f"Reference value{location} is an unresolved proxy.",
                feature,
            )
            return

        expected_class = feature.eType
        actual_class = value.eClass

        if isinstance(expected_class, EClass):
            try:
                type_is_valid = expected_class.isSuperTypeOf(actual_class)
            except Exception:
                type_is_valid = (
                    actual_class is expected_class
                    or expected_class in actual_class.eAllSuperTypes()
                )

            if not type_is_valid:
                self.error(
                    obj,
                    f"Reference value{location} has type "
                    f"'{actual_class.name}', but '{expected_class.name}' "
                    f"or one of its subclasses is required.",
                    feature,
                )

        if feature.containment:
            try:
                container = value.eContainer()
            except Exception:
                container = getattr(value, "eContainer", lambda: None)()

            if container is not obj:
                actual_container = (
                    self.object_path(container)
                    if isinstance(container, EObject)
                    else "None"
                )

                self.error(
                    obj,
                    f"Contained object{location} has an incorrect container: "
                    f"{actual_container}.",
                    feature,
                )

    def validate_opposite(
        self,
        obj: EObject,
        feature: EReference,
        referenced_object: Any,
        index: Optional[int] = None,
    ) -> None:
        opposite = feature.eOpposite

        if opposite is None or not isinstance(referenced_object, EObject):
            return

        location = f" at index {index}" if index is not None else ""

        try:
            opposite_value = referenced_object.eGet(opposite)
        except Exception as exc:
            self.error(
                obj,
                f"Cannot read opposite reference "
                f"'{opposite.name}'{location}: {exc}",
                feature,
            )
            return

        if opposite.many:
            try:
                opposite_is_valid = obj in opposite_value
            except TypeError:
                opposite_is_valid = False
        else:
            opposite_is_valid = opposite_value is obj

        if not opposite_is_valid:
            self.error(
                obj,
                f"Opposite reference '{opposite.name}' is inconsistent"
                f"{location}.",
                feature,
            )

    def validate_container(self, obj: EObject) -> None:
        try:
            container = obj.eContainer()
        except Exception:
            return

        if container is None:
            return

        try:
            containing_feature = obj.eContainmentFeature()
        except Exception:
            containing_feature = None

        if containing_feature is None:
            self.error(
                obj,
                "Object has a container but no containment feature.",
            )
            return

        if not isinstance(containing_feature, EReference):
            self.error(
                obj,
                "Containment feature is not an EReference.",
            )
            return

        if not containing_feature.containment:
            self.error(
                obj,
                f"Containing feature '{containing_feature.name}' is not "
                f"marked as containment.",
            )

        try:
            parent_value = container.eGet(containing_feature)
        except Exception as exc:
            self.error(
                obj,
                f"Cannot inspect containing feature: {exc}",
            )
            return

        if containing_feature.many:
            if obj not in parent_value:
                self.error(
                    obj,
                    f"Container does not contain this object through "
                    f"'{containing_feature.name}'.",
                )
        elif parent_value is not obj:
            self.error(
                obj,
                f"Container does not reference this object through "
                f"'{containing_feature.name}'.",
            )

    def validate_uniqueness(
        self,
        obj: EObject,
        feature: EStructuralFeature,
        values: list[Any],
    ) -> None:
        for first_index in range(len(values)):
            for second_index in range(first_index + 1, len(values)):
                if self.values_equal(
                    values[first_index],
                    values[second_index],
                ):
                    self.error(
                        obj,
                        f"Duplicate values at indices {first_index} and "
                        f"{second_index}; the feature is unique.",
                        feature,
                    )

    @staticmethod
    def values_equal(first: Any, second: Any) -> bool:
        if isinstance(first, EObject) or isinstance(second, EObject):
            return first is second

        try:
            return first == second
        except Exception:
            return first is second

    @staticmethod
    def is_proxy(obj: EObject) -> bool:
        proxy_path = getattr(obj, "_proxy_path", None)

        if proxy_path:
            return True

        try:
            return bool(obj.eIsProxy())
        except (AttributeError, TypeError):
            return False

    def object_path(self, obj: Optional[EObject]) -> str:
        if obj is None:
            return "<unknown>"

        segments: list[str] = []
        current: Optional[EObject] = obj
        visited: set[int] = set()

        while current is not None and id(current) not in visited:
            visited.add(id(current))

            eclass = getattr(current, "eClass", None)
            class_name = getattr(eclass, "name", type(current).__name__)

            try:
                container = current.eContainer()
            except Exception:
                container = None

            if container is None:
                segments.append(class_name)
                break

            try:
                feature = current.eContainmentFeature()
            except Exception:
                feature = None

            if feature is None:
                segments.append(class_name)
                current = container
                continue

            segment = feature.name

            if feature.many:
                try:
                    siblings = list(container.eGet(feature))
                    index = next(
                        (
                            position
                            for position, sibling in enumerate(siblings)
                            if sibling is current
                        ),
                        -1,
                    )
                    segment += f"[{index}]"
                except Exception:
                    segment += "[?]"

            segment += f"<{class_name}>"
            segments.append(segment)
            current = container

        return "/" + "/".join(reversed(segments))


def walk_packages(root: EPackage) -> Iterable[EPackage]:
    """Return the root package and every nested EPackage."""
    yield root

    for classifier in root.eClassifiers:
        if isinstance(classifier, EPackage):
            yield from walk_packages(classifier)

    for subpackage in root.eSubpackages:
        yield from walk_packages(subpackage)


def register_package_recursive(
    resource_set: ResourceSet,
    package: EPackage,
) -> None:
    for current_package in walk_packages(package):
        if current_package.nsURI:
            resource_set.metamodel_registry[
                current_package.nsURI
            ] = current_package


def load_metamodel(
    resource_set: ResourceSet,
    ecore_file: Path,
) -> list[EPackage]:
    resource = resource_set.get_resource(URI(str(ecore_file.resolve())))

    packages = [
        element
        for element in resource.contents
        if isinstance(element, EPackage)
    ]

    if not packages:
        raise ValueError(
            f"No EPackage was found in metamodel '{ecore_file}'."
        )

    for package in packages:
        register_package_recursive(resource_set, package)

    return packages


def load_instance(
    resource_set: ResourceSet,
    xmi_file: Path,
) -> XMIResource:
    resource = resource_set.get_resource(URI(str(xmi_file.resolve())))

    if not resource.contents:
        raise ValueError(
            f"Instance model '{xmi_file}' contains no root objects."
        )

    return resource


def validate_files(
    ecore_file: Path,
    xmi_file: Path,
) -> tuple[bool, list[ValidationIssue]]:
    resource_set = ResourceSet()

    # Ensure .xmi files use the XMI serializer/deserializer.
    resource_set.resource_factory["xmi"] = XMIResource
    resource_set.resource_factory["ecore"] = XMIResource

    load_metamodel(resource_set, ecore_file)
    instance_resource = load_instance(resource_set, xmi_file)

    validator = EcoreInstanceValidator()
    issues = validator.validate_resource(instance_resource.contents)

    errors = [
        issue
        for issue in issues
        if issue.severity == "ERROR"
    ]

    return len(errors) == 0, issues


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate an XMI model instance against an Ecore metamodel."
        )
    )

    parser.add_argument(
        "ecore",
        type=Path,
        help="Path to the .ecore metamodel.",
    )

    parser.add_argument(
        "xmi",
        type=Path,
        help="Path to the .xmi model instance.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    if not args.ecore.is_file():
        print(
            f"Metamodel file does not exist: {args.ecore}",
            file=sys.stderr,
        )
        return 2

    if not args.xmi.is_file():
        print(
            f"Model instance file does not exist: {args.xmi}",
            file=sys.stderr,
        )
        return 2

    try:
        valid, issues = validate_files(args.ecore, args.xmi)
    except Exception as exc:
        print(
            "The model could not be loaded or validated.",
            file=sys.stderr,
        )
        print(
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    if issues:
        for issue in issues:
            print(issue)

    if valid:
        print(
            f"VALID: '{args.xmi}' conforms to '{args.ecore}'."
        )
        return 0

    error_count = sum(
        issue.severity == "ERROR"
        for issue in issues
    )

    warning_count = sum(
        issue.severity == "WARNING"
        for issue in issues
    )

    print(
        f"INVALID: {error_count} error(s) and "
        f"{warning_count} warning(s) found."
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())