"""Errors raised when Periods do not align."""

from rangekeeper.shared.errors import ContractError


class AlignmentError(ContractError):
    """Periods or Flow coordinates do not align.

    ``code`` is an ``alignment.*`` code, given by keyword:
    ``Code.ALIGNMENT_CROSSES`` when a Period crosses the bounds of a selection,
    ``Code.ALIGNMENT_PARTIAL`` when Periods end with a partial Period,
    ``Code.ALIGNMENT_MIXED`` when Flows mix dated and period amounts,
    ``Code.ALIGNMENT_DIFFER`` when Flows that must match have other
    coordinates, ``Code.ALIGNMENT_DUPLICATE`` when one Flow repeats a
    coordinate, and ``Code.ALIGNMENT_GAP`` when Periods leave a gap.
    ``values`` gives the Periods and dates as ISO text.
    """


__all__ = ["AlignmentError"]
