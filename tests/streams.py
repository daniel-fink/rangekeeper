"""Name Flows by position in a Stream, for tests of Stream operations."""

from rangekeeper.flow import Stream


def lines(flows, **policies):
    """Return a Stream whose line names are the positions of the Flows."""
    return Stream(flows={str(i): flow for i, flow in enumerate(flows)}, **policies)
