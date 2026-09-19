"""Reusable graph-building capabilities, with optional declarative execution.

Keep package import lightweight: adapters can use ingestion without importing
workflow configuration, composition, or the runner.
"""

from importlib import import_module

__all__ = ["WorkflowResult", "WorkflowSpec", "load", "run", "schema"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    module = "runtime" if name in {"WorkflowResult", "run"} else "specification"
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value
