import re


class SysMLValidator:
    def __init__(self):
        self.errors = []

    def validate(self, text: str):
        self.errors = []

        self._check_package(text)
        self._check_braces(text)

        part_defs = self._parse_part_definitions(text)
        self._check_duplicate_parts(part_defs)

        known_types = set(part_defs.keys())
        known_types.update(["String", "Real", "Integer", "Boolean"])

        for name, body in part_defs.items():
            self._check_attributes(name, body)
            self._check_specialization(name, body, known_types)
            self._check_part_usages(name, body, known_types)

        return self.errors

    def _check_package(self, text):
        if not re.search(r'package\s+\w+\s*\{', text):
            self.errors.append("Missing package declaration")

    def _check_braces(self, text):
        if text.count("{") != text.count("}"):
            self.errors.append("Unbalanced braces")

    def _parse_part_definitions(self, text):
        parts = {}

        pattern = re.compile(
            r'(?:abstract\s+)?part\s+def\s+(\w+)'
            r'(?:\s+specializes\s+\w+)?'
            r'\s*\{',
            re.MULTILINE
        )

        matches = list(pattern.finditer(text))

        for i, match in enumerate(matches):
            name = match.group(1)

            start = match.end()
            depth = 1
            pos = start

            while pos < len(text) and depth > 0:
                if text[pos] == "{":
                    depth += 1
                elif text[pos] == "}":
                    depth -= 1
                pos += 1

            body = text[start:pos - 1]
            parts[name] = body

        return parts

    def _check_duplicate_parts(self, parts):
        names = list(parts.keys())
        if len(names) != len(set(names)):
            self.errors.append("Duplicate part definitions")

    def _check_attributes(self, part_name, body):
        attrs = re.findall(
            r'attribute\s+(\w+)\s*:\s*(\w+)\s*;',
            body
        )

        seen = set()

        for attr, attr_type in attrs:
            if attr in seen:
                self.errors.append(
                    f"Duplicate attribute '{attr}' in '{part_name}'"
                )
            seen.add(attr)

    def _check_specialization(self, part_name, body, known_types):
        m = re.search(
            rf'part\s+def\s+{part_name}\s+specializes\s+(\w+)',
            body
        )

        if m:
            parent = m.group(1)
            if parent not in known_types:
                self.errors.append(
                    f"Unknown parent '{parent}' in '{part_name}'"
                )

    def _check_part_usages(self, part_name, body, known_types):
        usages = re.findall(
            r'part\s+(\w+)\s*:\s*(\w+)\s*;',
            body
        )

        seen = set()

        for usage, usage_type in usages:

            if usage in seen:
                self.errors.append(
                    f"Duplicate part usage '{usage}' in '{part_name}'"
                )
            seen.add(usage)

            if usage_type not in known_types:
                self.errors.append(
                    f"Unknown type '{usage_type}' in '{part_name}'"
                )


def check_sysml_file(path):

    with open(path, "r") as f:
        text = f.read()

    validator = SysMLValidator()

    errors = validator.validate(text)

    if errors:
        print("❌ Validation errors:")
        for e in errors:
            print(" -", e)
        return False

    print("Valid SysML metamodel")
    return True


if __name__ == "__main__":

    sysml_file = "metamodel_merged.sysml"

    check_sysml_file(sysml_file)