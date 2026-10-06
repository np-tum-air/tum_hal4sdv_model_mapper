# Model Interoperability Evaluation Scripts

This directory contains evaluation scripts used to assess the semantic
correctness of LLM-generated model transformations and metamodel merging
results across **Ecore/XMI** and **SysML v2**.

## Requirements

-   Python 3.8 or newer
-   No additional Python packages are required.

Run the scripts from a terminal or PowerShell in the directory
containing the evaluation files.

------------------------------------------------------------------------

## 1. Model Instance Semantic Mapping

**Script:** `semantic_mapping_eval.py`

This script evaluates semantic preservation when a model instance is
transformed between XMI/Ecore and SysML v2 representations.

The evaluation considers:

-   **Components / model instances**
-   **Attributes**
-   **Attribute values**

Equivalent representation-specific names can be defined as semantic
aliases in the script. For example:

``` python
ATTRIBUTE_ALIASES = {
    "fov": "fieldOfView",
}
```

Numeric values are normalized so that representation differences such as
`120` and `120.0` do not cause a mismatch.

### Usage

``` bash
python semantic_mapping_eval.py vehicle_control.xmi vehicle_control.sysml
```

On systems where Python is invoked as `python3`:

``` bash
python3 semantic_mapping_eval.py vehicle_control.xmi vehicle_control.sysml
```

Optional JSON output:

``` bash
python semantic_mapping_eval.py vehicle_control.xmi vehicle_control.sysml --json results.json
```

### Example output

``` text
SEMANTIC MAPPING EVALUATION
========================================================================
Aspect                       XMI     SysML     Matched       Score
------------------------------------------------------------------------
Components / instances         6         6         6/6      100.0%
Attributes                    11        11       11/11      100.0%
Attribute values              11        11       11/11      100.0%
------------------------------------------------------------------------
Overall semantic mapping                           28/28      100.0%
```

The overall semantic mapping score is calculated from the number of
expected semantic elements preserved in the transformed model.

------------------------------------------------------------------------

## 2. Metamodel Merging Semantic Evaluation

**Script:** `metamodel_merge_eval.py`

This script evaluates whether a generated merged metamodel preserves the
semantic **union of two source metamodels**.

Supported scenarios are:

1.  **Ecore + Ecore → Ecore**
2.  **Ecore + SysML v2 → SysML v2**
3.  **SysML v2 + SysML v2 → SysML v2**

The evaluator considers:

-   **Classes / SysML part definitions**
-   **Attributes**
-   **Relationships / contained parts**
-   **Inheritance relationships**

If an equivalent element occurs in both source metamodels, it is counted
only once in the expected semantic union.

Let `S1` and `S2` denote the semantic elements extracted from the two
source metamodels. The expected merged content is:

``` text
U = S1 ∪ S2
```

For a generated merged metamodel `M`, semantic preservation is evaluated
as:

``` text
Semantic Matching = |U ∩ M| / |U| × 100%
```

### Ecore + Ecore → Ecore

``` bash
python metamodel_merge_eval.py source1.ecore source2.ecore merged.ecore
```

### Ecore + SysML v2 → SysML v2

``` bash
python metamodel_merge_eval.py source.ecore source.sysml merged.sysml
```

### SysML v2 + SysML v2 → SysML v2

``` bash
python metamodel_merge_eval.py source1.sysml source2.sysml merged.sysml
```

### Detailed output

Use `--details` to display all extracted source elements, the expected
semantic union, and the elements extracted from the generated merged
metamodel:

``` bash
python metamodel_merge_eval.py source.ecore source.sysml merged.sysml --details
```

Optional JSON output:

``` bash
python metamodel_merge_eval.py source.ecore source.sysml merged.sysml --json results.json
```

### Example output

``` text
METAMODEL MERGING SEMANTIC EVALUATION
==============================================================================
Aspect                  Expected union   Generated     Matched       Score
------------------------------------------------------------------------------
Classes                              6           6         6/6      100.0%
Attributes                           9           9         9/9      100.0%
Relationships                        5           5         5/5      100.0%
Inheritance                          4           4         4/4      100.0%
------------------------------------------------------------------------------
Overall semantic match                                    24/24      100.0%
```

The script additionally reports **missing elements** and **additional
generated elements**, which helps identify information loss or
unexpected concepts introduced during merging.

------------------------------------------------------------------------

## Recommended Directory Structure

``` text
evaluation/
├── README.md
├── semantic_mapping_eval.py
├── metamodel_merge_eval.py
├── instances/
│   ├── vehicle_control.xmi
│   └── vehicle_control.sysml
└── metamodels/
    ├── source1.ecore
    ├── source2.ecore
    ├── source1.sysml
    ├── source2.sysml
    ├── merged.ecore
    └── merged.sysml
```

When the input files are stored in subdirectories, provide their
relative paths:

``` bash
python semantic_mapping_eval.py instances/vehicle_control.xmi instances/vehicle_control.sysml
```

or:

``` bash
python metamodel_merge_eval.py metamodels/source1.ecore metamodels/source2.ecore metamodels/merged.ecore
```

------------------------------------------------------------------------

## Semantic Aliases

Ecore and SysML v2 models may use different names for semantically
equivalent concepts. The scripts therefore contain alias dictionaries
that can be extended for a particular evaluation dataset.

For example:

``` python
NAME_ALIASES = {
    "fov": "fieldOfView",
}
```

Aliases should only be added when the corresponding elements are known
to represent the same domain concept.

------------------------------------------------------------------------

## Interpretation of Results

A score of **100%** means that all expected semantic elements from the
reference model or semantic union were found in the generated result.

A lower score indicates that one or more expected components, classes,
attributes, values, relationships, or inheritance relations were not
preserved.

The semantic score evaluates **content preservation**. It is independent
of syntactic correctness; syntax/conformance validation should therefore
be performed separately using the corresponding Ecore/XMI or SysML v2
validator.
