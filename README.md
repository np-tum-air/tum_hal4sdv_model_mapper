# LLM-Driven Model Mapping and Validation

This repository provides an LLM-based framework for automatic model transformation and validation between **Ecore/XMI** and **SysML v2**.

## Components

- **model_mapper_workflow.py** – LLM-based model transformation
- **instance_validator.py** – Ecore/XMI validator (PyEcore)
- **sysml_instance_validator.py** – SysML v2 validator

---

# Summary

- Supports Ecore and SysML v2 transformations.
- Uses OpenAI-compatible LLMs.
- Reads API settings from `.env`.
- Automatically cleans LLM Markdown output.
- Validates generated models using dedicated Ecore and SysML validators.
- Suitable for homogeneous and heterogeneous model transformations.

# Requirements

- Python 3.10+
- OpenAI-compatible inference server

Install dependencies:

```bash
pip install openai python-dotenv pillow pyecore
```

Create a `.env` file:

```text
OPENAI_API_KEY=<your_api_key>
OPENAI_BASE_URL=http://<server>/inference
```

---

# 1. model_mapper_workflow.py

Transforms model instances using an LLM.

Supported transformations:

- Ecore → Ecore
- Ecore → SysML v2
- SysML v2 → SysML v2
- SysML v2 → Ecore

## Usage

```bash
python3 model_mapper_workflow.py <instance_model> <target_model> <ecore|sysml>
```

Examples:

```bash
python3 model_mapper_workflow.py instance.xmi target.ecore ecore

python3 model_mapper_workflow.py instance.xmi target.sysml sysml

python3 model_mapper_workflow.py instance.sysml target.ecore ecore

python3 model_mapper_workflow.py instance.sysml target.sysml sysml
```

Generated output:

- `<input>_mapped.xmi`
- `<input>_mapped.sysml`

The workflow automatically removes Markdown code fences returned by the LLM.

---

# 2. instance_validator.py

Validates an XMI instance against an Ecore metamodel using **PyEcore**.

## Usage

```bash
python3 instance_validator.py target.ecore instance_mapped.xmi
```

Checks include:

- XML well-formedness
- metamodel conformance
- containment hierarchy
- multiplicities
- mandatory features
- datatype compatibility
- references
- uniqueness constraints

Exit codes:

- `0` – valid
- `1` – validation errors
- `2` – loading/parsing error

---

# 3. sysml_instance_validator.py

Validates textual SysML v2 instances against user-defined `part def` and `port def` definitions.

## Usage

```bash
python3 sysml_instance_validator.py target.sysml instance_mapped.sysml
```

Generate a JSON report:

```bash
python3 sysml_instance_validator.py target.sysml instance.sysml --output report.json
```

Checks include:

- typed part usages
- port usages
- declared types
- attributes
- multiplicities
- required features
- primitive value types

Exit codes:

- `0` – valid
- `1` – validation errors

---

# Typical Workflow

**Ecore → Ecore**

```text
instance.xmi
      │
      ▼
model_mapper_workflow.py
      │
      ▼
mapped.xmi
      │
      ▼
instance_validator.py
```

**Ecore → SysML**

```text
instance.xmi
      │
      ▼
model_mapper_workflow.py
      │
      ▼
mapped.sysml
      │
      ▼
sysml_instance_validator.py
```

**SysML → SysML**

```text
instance.sysml
      │
      ▼
model_mapper_workflow.py
      │
      ▼
mapped.sysml
      │
      ▼
sysml_instance_validator.py
```

**SysML → Ecore**

```text
instance.sysml
      │
      ▼
model_mapper_workflow.py
      │
      ▼
mapped.xmi
      │
      ▼
instance_validator.py
```

---

