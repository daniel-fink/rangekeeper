"""Codes of the diagnostics and errors that Rangekeeper reports (ADR-016).

Read a finding by its ``code`` and its structured fields, never by its message.
"""

from rangekeeper.shared.codes import Code

__all__ = ["Code"]
