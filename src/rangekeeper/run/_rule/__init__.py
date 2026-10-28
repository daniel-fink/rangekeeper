"""Rule semantics that the evaluator and the trace check share (internal).

The exact Boolean truth of a condition and the date when an observation becomes
available are in ``run`` because the trace check of a stored Run needs them, and
``run`` is below ``execution``.
"""
