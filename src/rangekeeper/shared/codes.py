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
    # A generated node check (ADR-011): a field value or a class rule of one record.
    STRUCTURE_VALUE = "structure.value"
    STRUCTURE_RULE = "structure.rule"
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
    RESOLVER_MISSING = "semantic.resolver"
    ROLE_MISSING = "semantic.role"
    UNIQUE = "semantic.unique"
    UNITS = "semantic.units"
    # Dimensional analysis (ADR-016): the two sides of an equation, the operands
    # of a sum, or a value and the quantity that fixes it have incompatible units.
    INCOMPATIBLE_UNITS = "incompatible_units"

    # Currency amounts (ADR-023): a magnitude whose type does not match its
    # units, and an amount with more than 15 significant digits.
    AMOUNT_DIGITS = "amount_digits"
    CURRENCY_AMOUNT = "currency_amount"

    # The local rules of one value type (ADR-011), as ``invariant.<kind>``.
    INVARIANT_DISTRIBUTION = "invariant.Distribution"
    INVARIANT_FLOW = "invariant.Flow"
    INVARIANT_MOVEMENT = "invariant.Movement"
    INVARIANT_PERIOD = "invariant.Period"
    INVARIANT_SPAN = "invariant.Span"

    # Batches of cases. ``BATCH_REQUIRED``: the call reads the cases of a batch,
    # and the Specification or Outcome has none. ``BATCH_UNSUPPORTED``: the call
    # takes one concrete Specification or one leaf Outcome, not a batch.
    BATCH_MODEL = "batch.model"
    BATCH_REQUIRED = "batch.required"
    BATCH_UNSUPPORTED = "batch.unsupported"

    # Periods and coordinates that do not align: a Period crosses the bounds of a
    # selection, Periods end with a partial Period, Flows mix dates and Periods,
    # coordinates differ or repeat, or Periods leave a gap.
    ALIGNMENT_CROSSES = "alignment.crosses"
    ALIGNMENT_PARTIAL = "alignment.partial"
    ALIGNMENT_MIXED = "alignment.mixed"
    ALIGNMENT_DIFFER = "alignment.differ"
    ALIGNMENT_DUPLICATE = "alignment.duplicate"
    ALIGNMENT_GAP = "alignment.gap"

    # References between records and documents.
    REFERENCE_AMBIGUOUS = "reference.ambiguous"
    REFERENCE_IDENTITY = "reference.identity"
    REFERENCE_KIND = "reference.kind"
    REFERENCE_MISSING = "reference.missing"
    REFERENCE_PREDICATE = "reference.predicate"

    # Execution findings that a Run records. ``ACTIVE_SIDE``: no active side
    # of each max or min call held at the solution of its affine problem.
    ACTIVE_SIDE = "active_side"
    ASSIGNMENT_REJECTED = "assignment_rejected"
    ATTEMPT_DEADLINE = "attempt_deadline"
    ATTEMPT_TIMING = "attempt_timing"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    BATCH_ACCOUNTING = "batch_accounting"
    CONSTRAINT_LIMIT = "constraint_limit"
    CONSTRAINT_RESIDUAL = "constraint_residual"
    ESTIMATES_UNUSED = "estimates_unused"
    FEASIBLE_CANDIDATE = "feasible_candidate"
    NONAFFINE_UNKNOWNS = "nonaffine_unknowns"
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

    # Errors outside validation and execution.
    DECODE = "decode"
    ENCODING = "encoding"
    EXTENSION_CONFLICT = "extension.conflict"
    EXTENSION_UNKNOWN = "extension.unknown"
    PUBLISHED_FILE = "published_file"
    REPLAY_UNAVAILABLE = "replay_unavailable"
    REVISION_CONFLICT = "revision_conflict"
    ROLLUP = "rollup"
    RULE_CAPABILITY = "rule_capability"
    SELECTION = "selection"
    TABLE = "table"
    UNSUPPORTED_VERSION = "unsupported_version"

    # Equation text: text that does not parse, and a function, method or member
    # that equation text cannot use.
    EQUATION_SYNTAX = "equation.syntax"
    EQUATION_FUNCTION = "equation.function"

    # A comparison of Outcomes that cannot pair or read its values.
    COMPARISON_BATCH = "comparison.batch"
    COMPARISON_CASES = "comparison.cases"
    COMPARISON_EMPTY = "comparison.empty"
    COMPARISON_SCALAR = "comparison.scalar"

    # A distribution of a batch's values that its kind of value does not have:
    # a Flow has no distribution, and a date has counts but no mean.
    DISTRIBUTION_VALUE = "distribution.value"

    # A selected graph that is not one rooted tree.
    HIERARCHY_CYCLE = "hierarchy.cycle"
    HIERARCHY_DISCONNECTED = "hierarchy.disconnected"
    HIERARCHY_EMPTY = "hierarchy.empty"
    HIERARCHY_MULTIPLE_PARENTS = "hierarchy.multiple_parents"
    HIERARCHY_PARALLEL_EDGES = "hierarchy.parallel_edges"
    HIERARCHY_ROOT_MISMATCH = "hierarchy.root_mismatch"
