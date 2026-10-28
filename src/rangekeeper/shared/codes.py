"""The codes of diagnostics and errors (ADR-016).

Each member's value is the code text that reports and Runs record. The values
are a wire contract: a renamed member keeps its value, and a changed value is a
breaking change. Code reads the code and the structured fields of a finding,
never its message.
"""

from enum import StrEnum, unique


@unique
class Code(StrEnum):
    """The code of a diagnostic or an error."""

    # Structural validation: the document is not JSON, or a JSON Schema keyword
    # fails. Each keyword member has the value ``structure.<keyword>``.
    STRUCTURE = "structure.schema"
    STRUCTURE_JSON = "structure.json"
    STRUCTURE_KIND = "structure.kind"
    STRUCTURE_ADDITIONAL_PROPERTIES = "structure.additionalProperties"
    STRUCTURE_ANY_OF = "structure.anyOf"
    STRUCTURE_CONST = "structure.const"
    STRUCTURE_CONTAINS = "structure.contains"
    STRUCTURE_DEPENDENT_REQUIRED = "structure.dependentRequired"
    STRUCTURE_ENUM = "structure.enum"
    STRUCTURE_EXCLUSIVE_MAXIMUM = "structure.exclusiveMaximum"
    STRUCTURE_EXCLUSIVE_MINIMUM = "structure.exclusiveMinimum"
    STRUCTURE_FORMAT = "structure.format"
    STRUCTURE_MAX_ITEMS = "structure.maxItems"
    STRUCTURE_MAX_LENGTH = "structure.maxLength"
    STRUCTURE_MAX_PROPERTIES = "structure.maxProperties"
    STRUCTURE_MAXIMUM = "structure.maximum"
    STRUCTURE_MIN_ITEMS = "structure.minItems"
    STRUCTURE_MIN_LENGTH = "structure.minLength"
    STRUCTURE_MIN_PROPERTIES = "structure.minProperties"
    STRUCTURE_MINIMUM = "structure.minimum"
    STRUCTURE_MULTIPLE_OF = "structure.multipleOf"
    STRUCTURE_NOT = "structure.not"
    STRUCTURE_ONE_OF = "structure.oneOf"
    STRUCTURE_PATTERN = "structure.pattern"
    STRUCTURE_REQUIRED = "structure.required"
    STRUCTURE_TYPE = "structure.type"
    STRUCTURE_UNEVALUATED_ITEMS = "structure.unevaluatedItems"
    STRUCTURE_UNEVALUATED_PROPERTIES = "structure.unevaluatedProperties"
    STRUCTURE_UNIQUE_ITEMS = "structure.uniqueItems"

    # Semantic validation of one document or a composition.
    CONTRACT = "semantic.contract"
    CONTAINMENT = "semantic.containment"
    CYCLE = "semantic.cycle"
    IDENTITY = "semantic.identity"
    MODEL_MISSING = "semantic.model"
    PREDICATE = "semantic.predicate"
    ROLE_MISSING = "semantic.role"
    UNIQUE = "semantic.unique"
    UNITS = "semantic.units"

    # Batches of cases.
    BATCH_MODEL = "batch.model"

    # References between records and documents.
    REFERENCE_IDENTITY = "reference.identity"
    REFERENCE_KIND = "reference.kind"
    REFERENCE_MISSING = "reference.missing"
    REFERENCE_PREDICATE = "reference.predicate"

    # Execution findings that a Run records.
    ASSIGNMENT_REJECTED = "assignment_rejected"
    ATTEMPT_DEADLINE = "attempt_deadline"
    ATTEMPT_TIMING = "attempt_timing"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    BATCH_ACCOUNTING = "batch_accounting"
    CONSTRAINT_LIMIT = "constraint_limit"
    CONSTRAINT_RESIDUAL = "constraint_residual"
    ESTIMATES_UNUSED = "estimates_unused"
    FEASIBLE_CANDIDATE = "feasible_candidate"
    NUMERICAL_FAILURE = "numerical_failure"
    NUMERICAL_REJECTION = "numerical_rejection"
    SETTINGS_ADJUSTED = "settings_adjusted"
    SOLVER_SCALING = "solver_scaling"
    SOLVER_TERMINATION = "solver_termination"
    SPECIFICATION_INVALID = "specification_invalid"
    SYMBOL_LIMIT = "symbol_limit"
    UNDERDETERMINED = "underdetermined"
    UNIQUENESS_NOT_ASSESSED = "uniqueness_not_assessed"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
