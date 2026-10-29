"""Errors raised when Periods do not align."""

from rangekeeper.shared.errors import ContractError


class AlignmentError(ContractError):
    """Periods do not align: a Period crosses a boundary, or a partition is partial.

    ``code`` is an ``alignment.*`` code, given by keyword:
    ``Code.ALIGNMENT_CROSSES`` when a Period crosses the bounds of a selection,
    and ``Code.ALIGNMENT_PARTIAL`` when Periods end with a partial Period.
    ``values`` gives the Periods and dates as ISO text.
    """


__all__ = ["AlignmentError"]
