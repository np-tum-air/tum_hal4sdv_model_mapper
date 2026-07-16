from pyecore.resources import ResourceSet, URI
from pyecore.ecore import EPackage, EClass, EReference, EEnum, EDataType


class EcoreValidator:
    def __init__(self):
        self.errors = []

    def validate(self, epackage: EPackage):
        """Validate an EPackage and its contents."""
        self._check_package(epackage)
        self._check_classifiers(epackage)

        # Recursively validate subpackages
        for sub in epackage.eSubpackages:
            self.validate(sub)

        return self.errors

    def _check_package(self, pkg: EPackage):
        if not pkg.name:
            self.errors.append("EPackage must have a name")
        if not pkg.nsURI:
            self.errors.append(f"EPackage '{pkg.name}' must have an nsURI")
        if not pkg.nsPrefix:
            self.errors.append(f"EPackage '{pkg.name}' must have an nsPrefix")

    def _check_classifiers(self, pkg: EPackage):
        seen = set()
        for classifier in pkg.eClassifiers:
            # Unique classifier names
            if not classifier.name:
                self.errors.append(f"Classifier without a name in package '{pkg.name}'")
            elif classifier.name in seen:
                self.errors.append(f"Duplicate classifier name '{classifier.name}' in package '{pkg.name}'")
            else:
                seen.add(classifier.name)

            if isinstance(classifier, EClass):
                self._check_eclass(classifier)
            elif isinstance(classifier, EEnum):
                self._check_eenum(classifier)
            elif isinstance(classifier, EDataType):
                self._check_edatatype(classifier)

    def _check_eclass(self, eclass: EClass):
        features_seen = set()
        for feature in eclass.eStructuralFeatures:
            # Feature naming
            if not feature.name:
                self.errors.append(f"Feature without name in EClass '{eclass.name}'")
            elif feature.name in features_seen:
                self.errors.append(f"Duplicate feature '{feature.name}' in EClass '{eclass.name}'")
            else:
                features_seen.add(feature.name)

            # Multiplicity sanity
            if feature.lowerBound < 0 or feature.upperBound < -1:
                self.errors.append(
                    f"Invalid multiplicity in {eclass.name}.{feature.name}: "
                    f"[{feature.lowerBound}..{feature.upperBound}]"
                )

            # EReference must have a type
            if isinstance(feature, EReference) and feature.eType is None:
                self.errors.append(
                    f"EReference '{feature.name}' in EClass '{eclass.name}' has no target type"
                )

    def _check_eenum(self, eenum: EEnum):
        if not eenum.eLiterals:
            self.errors.append(f"EEnum '{eenum.name}' has no literals")

    def _check_edatatype(self, edatatype: EDataType):
        if not edatatype.instanceClassName:
            self.errors.append(f"EDataType '{edatatype.name}' has no instanceClassName")


def check_ecore_file(path: str):
    rset = ResourceSet()
    try:
        resource = rset.get_resource(URI(path))
        model = resource.contents[0]  # root EPackage
    except Exception as e:
        print(f"❌ Failed to load Ecore file: {e}")
        return False

    validator = EcoreValidator()
    errors = validator.validate(model)

    if errors:
        print("❌ Validation errors:")
        for err in errors:
            print(" -", err)
        return False
    else:
        print("Valid metamodel")
        return True


if __name__ == "__main__":
    # Replace with your .ecore path
    ecore_file = "metamodel_merged.ecore"
    check_ecore_file(ecore_file)
