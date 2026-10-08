"""The explicit, closed set of RK workflow capabilities.

This is the only assembly point that imports concrete integrations. No scanning,
entry points, registration decorators or configuration-selected imports are used.
"""

from rangekeeper.adapters.excel import workflow as excel

from rangekeeper.workflow import _table_operations as tables

OPERATIONS = {**excel.OPERATIONS, **tables.OPERATIONS}
SOURCE_CHECKS = excel.SOURCE_CHECKS
REFERENCE_FORMATTERS = (excel.format_reference,)
RECORD_FORMATTERS = (excel.record_reference,)
