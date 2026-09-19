"""Resolve bounded declarations for both composition and checks.

These functions retain supporting Claims alongside values; they do not construct
graph objects or require workflow execution.
"""

from string import Formatter

from rangekeeper.graph.operation import _Failure

from ._declarations import fields, sequence, text
from .ingestion import tabular
from .ingestion.predicates import equal


def binding(spec, row, evidence, outputs):
    """Resolves a mapping to both its value and supporting Claims so composition
    and checks do not detach graph assertions from their evidence.
    """
    if "value" in spec:
        return spec["value"], ()
    selected = outputs[spec["evidence"]] if "evidence" in spec else evidence
    if selected is None:
        raise _Failure("missing_evidence", "No row context for binding")
    if "evidence" in spec:
        if len(selected.data.rows) != 1:
            raise _Failure(
                "ambiguous_evidence", "Named context must contain exactly one row"
            )
        selected_row = selected.data.rows[0]
    else:
        selected_row = row
    col = spec["column"]
    if col not in selected.data.columns:
        raise _Failure("missing_column", f"Binding references missing column {col}")
    c = tabular.claim(selected, selected_row.id, col)
    return c.value, (c,)


def condition(spec, row, evidence, outputs):
    """Makes omission and inclusion policy explicit while limiting comparisons to
    declared values and availability.
    """
    if spec is None:
        return True
    value, _ = binding(spec["binding"], row, evidence, outputs)
    if "equals" in spec:
        return equal(value, spec["equals"])
    if "in" in spec:
        return any(equal(value, v) for v in spec["in"])
    return (value is not None) == spec["available"]


def validate_binding(value, seen):
    fields(value, {"value", "column", "evidence"})
    if "value" in value:
        if len(value) != 1:
            raise ValueError("Literal bindings cannot reference evidence")
    else:
        text(value.get("column"))
        if "evidence" in value and seen.get(value["evidence"]) != "table":
            raise ValueError("Binding names unknown Evidence")


def validate_condition(value, seen):
    if value is None:
        return
    fields(value, {"binding", "equals", "in", "available"}, {"binding"})
    if len(value) != 2:
        raise ValueError("A condition requires exactly one comparison")
    validate_binding(value["binding"], seen)
    if "available" in value and type(value["available"]) is not bool:
        raise TypeError("available must be boolean")
    if "in" in value:
        sequence(value["in"])


def template(text_value, values):
    """Builds declared business keys from plain named fields without permitting
    attribute access or executable expressions.
    """
    for _, key, spec, conversion in Formatter().parse(text_value):
        if key is not None and (key not in values or spec or conversion):
            raise ValueError("Only declared plain template keys are supported")
    return text_value.format_map(values)
