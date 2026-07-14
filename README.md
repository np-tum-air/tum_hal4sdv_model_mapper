# HAL4SDV Model Mapper

This repository contains two Python utilities for LLM-assisted model transformation and validation of EMF models.

## Components

### 1. `mapper.py`

Transforms an XMI model instance to comply with a target Ecore metamodel using a Large Language Model (LLM).

The script:

1. Reads an input XMI instance model.
2. Reads a target Ecore metamodel.
3. Sends both to an OpenAI-compatible LLM endpoint.
4. Generates a new XMI instance intended to conform to the target metamodel.
5. Saves the generated model as `<input>_mapped.xmi`.
6. Automatically validates the generated model using `instance_validator.py`.

Example:

```bash
python mapper.py instance_model.xmi target_metamodel.ecore
```

Generated output:

```
instance_model_mapped.xmi
```

---

### 2. `instance_validator.py`

Validates an XMI model instance against an Ecore metamodel using PyEcore.

The validator checks:

* required attributes and references
* multiplicity constraints
* attribute datatypes
* enumeration values
* reference types
* containment consistency
* opposite references
* uniqueness constraints
* abstract class instantiation
* unresolved proxies

Example:

```bash
python instance_validator.py target_metamodel.ecore instance_model_mapped.xmi
```

Possible exit codes:

| Code | Meaning                  |
| ---- | ------------------------ |
| 0    | Model is valid           |
| 1    | Validation errors found  |
| 2    | Loading or parsing error |

---

# Requirements

* Python 3.10+
* PyEcore
* OpenAI Python SDK
* Pillow
* python-dotenv

Install dependencies:

```bash
pip install pyecore openai pillow python-dotenv
```

---

# Configuration

Create a `.env` file:

```text
OPENAI_API_KEY=<your_api_key>
OPENAI_BASE_URL=http://131.159.60.153:3000/inference
OPENAI_MODEL=Qwen/Qwen3.5-122B-A10B
```

Alternatively, the API key can be specified directly in `mapper.py`.

---

# Usage

## Transform a model

```bash
python mapper.py source.xmi target.ecore
```

Workflow:

```
source.xmi
      │
      ▼
Read source model
      │
      ▼
Read target metamodel
      │
      ▼
LLM mapping
      │
      ▼
source_mapped.xmi
      │
      ▼
Automatic validation
```

---

## Validate an existing model

```bash
python instance_validator.py target.ecore source_mapped.xmi
```

Example output:

```
VALID: 'source_mapped.xmi' conforms to 'target.ecore'.
```

or

```
[ERROR] /Root/items[0]<Book>.title:
Required attribute must be set.

INVALID: 1 error(s) and 0 warning(s) found.
```

---

# Project Structure

```
.
├── mapper.py
├── instance_validator.py
├── instance_model.xmi
├── target_metamodel.ecore
├── instance_model_mapped.xmi
├── .env
└── README.md
```

---

# Overall Workflow

```
             instance_model.xmi
                     │
                     ▼
             ┌─────────────────┐
             │    mapper.py     │
             │                 │
             │  Reads XMI      │
             │  Reads Ecore    │
             │  Calls the LLM  │
             └────────┬────────┘
                      │
                      ▼
          instance_model_mapped.xmi
                      │
                      ▼
        ┌──────────────────────────┐
        │ instance_validator.py    │
        │                          │
        │ Loads Ecore              │
        │ Loads generated XMI      │
        │ Checks EMF constraints   │
        └────────────┬─────────────┘
                     │
          VALID / INVALID report
```
# HAL4SDV Model Mapper

This repository contains two Python utilities for LLM-assisted model transformation and validation of EMF models.

## Components

### 1. `mapper.py`

Transforms an XMI model instance to comply with a target Ecore metamodel using a Large Language Model (LLM).

The script:

1. Reads an input XMI instance model.
2. Reads a target Ecore metamodel.
3. Sends both to an OpenAI-compatible LLM endpoint.
4. Generates a new XMI instance intended to conform to the target metamodel.
5. Saves the generated model as `<input>_mapped.xmi`.
6. Automatically validates the generated model using `instance_validator.py`.

Example:

```bash
python mapper.py instance_model.xmi target_metamodel.ecore
```

Generated output:

```
instance_model_mapped.xmi
```

---

### 2. `instance_validator.py`

Validates an XMI model instance against an Ecore metamodel using PyEcore.

The validator checks:

* required attributes and references
* multiplicity constraints
* attribute datatypes
* enumeration values
* reference types
* containment consistency
* opposite references
* uniqueness constraints
* abstract class instantiation
* unresolved proxies

Example:

```bash
python instance_validator.py target_metamodel.ecore instance_model_mapped.xmi
```

Possible exit codes:

| Code | Meaning                  |
| ---- | ------------------------ |
| 0    | Model is valid           |
| 1    | Validation errors found  |
| 2    | Loading or parsing error |

---

# Requirements

* Python 3.10+
* PyEcore
* OpenAI Python SDK
* Pillow
* python-dotenv

Install dependencies:

```bash
pip install pyecore openai pillow python-dotenv
```

---

# Configuration

Create a `.env` file:

```text
OPENAI_API_KEY=<your_api_key>
OPENAI_BASE_URL=http://131.159.60.153:3000/inference
OPENAI_MODEL=Qwen/Qwen3.5-122B-A10B
```

Alternatively, the API key can be specified directly in `mapper.py`.

---

# Usage

## Transform a model

```bash
python mapper.py source.xmi target.ecore
```

Workflow:

```
source.xmi
      │
      ▼
Read source model
      │
      ▼
Read target metamodel
      │
      ▼
LLM mapping
      │
      ▼
source_mapped.xmi
      │
      ▼
Automatic validation
```

---

## Validate an existing model

```bash
python instance_validator.py target.ecore source_mapped.xmi
```

Example output:

```
VALID: 'source_mapped.xmi' conforms to 'target.ecore'.
```

or

```
[ERROR] /Root/items[0]<Book>.title:
Required attribute must be set.

INVALID: 1 error(s) and 0 warning(s) found.
```

---

# Project Structure

```
.
├── mapper.py
├── instance_validator.py
├── instance_model.xmi
├── target_metamodel.ecore
├── instance_model_mapped.xmi
├── .env
└── README.md
```

---

# Overall Workflow

```
             instance_model.xmi
                     │
                     ▼
             ┌─────────────────┐
             │    mapper.py     │
             │                 │
             │  Reads XMI      │
             │  Reads Ecore    │
             │  Calls the LLM  │
             └────────┬────────┘
                      │
                      ▼
          instance_model_mapped.xmi
                      │
                      ▼
        ┌──────────────────────────┐
        │ instance_validator.py    │
        │                          │
        │ Loads Ecore              │
        │ Loads generated XMI      │
        │ Checks EMF constraints   │
        └────────────┬─────────────┘
                     │
          VALID / INVALID report
```

### 3. `sysml_instance_validator.py`

### Overview

The **SysML Model Instance Validator** verifies that a SysML v2 model instance conforms to a user-defined SysML model. It is intended for validating LLM-generated SysML instances without requiring full SysML metamodel validation.

The validator performs structural validation by comparing an instance model against the corresponding type definitions.

### Validation Scope

The validator currently checks:

* Existence of referenced `part def` and `port def` types.
* Correct usage of user-defined parts and ports.
* Presence of required features.
* Attribute existence.
* Primitive attribute value types (`Boolean`, `Integer`, `Natural`, `Real`, `Rational`, `String`).
* Nested part and port structures.
* Multiplicity constraints.

The validator does **not** currently perform:

* Full SysML v2 language validation.
* KerML semantic validation.
* Inheritance or specialization checking.
* Constraint or expression evaluation.
* Behavioral model validation (activities, states, actions, interactions).
* Connection or interface compatibility checking.

### Input Files

The validator requires two SysML v2 textual models:

1. **Definition model** – contains the user-defined structure (`part def`, `port def`, attributes, and feature declarations).
2. **Instance model** – contains one or more model instances that should conform to the definition model.

Example:

```text
VehicleDefinitions.sysml
VehicleInstance.sysml
```

### Usage

```bash
python sysml_instance_validator.py VehicleDefinitions.sysml VehicleInstance.sysml
```

To save the validation report:

```bash
python sysml_instance_validator.py \
    VehicleDefinitions.sysml \
    VehicleInstance.sysml \
    --output validation_report.json
```

### Output

The validator produces a JSON report containing:

* validation status (`valid`)
* parsed type definitions
* discovered model instances
* validation errors
* warnings

Example:

```json
{
  "valid": true,
  "definition_file": "VehicleDefinitions.sysml",
  "instance_file": "VehicleInstance.sysml",
  "definitions": [
    "Battery",
    "ElectricalPort",
    "ElectricMotor",
    "ElectricVehicle"
  ],
  "instances": [
    "myVehicle"
  ],
  "errors": [],
  "warnings": []
}
```

Example of an invalid model:

```json
{
  "valid": false,
  "errors": [
    {
      "severity": "ERROR",
      "path": "myVehicle.motor",
      "message": "Required feature 'motor' is missing."
    }
  ]
}
```

### Typical Workflow

```text
User-defined SysML model
        │
        ▼
VehicleDefinitions.sysml
        │
        ▼
LLM-generated instance
        │
        ▼
VehicleInstance.sysml
        │
        ▼
SysML Instance Validator
        │
        ▼
JSON validation report
```

This workflow is particularly suitable for validating automatically generated SysML v2 instances produced by large language models before further processing or transformation.
