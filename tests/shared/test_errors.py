"""The error hierarchy of ``rangekeeper.errors`` (ADR-016)."""

import importlib
import inspect
import pkgutil
from uuid import uuid4

import pytest

import rangekeeper
from rangekeeper import errors
from rangekeeper.errors import Code, RangekeeperError
from rangekeeper.model.system import HierarchyError
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from tests.contracts import api


def public_errors():
    """Return each Exception class that a public package exports."""
    found = set()
    for package in api.PACKAGES:
        module = importlib.import_module(package)
        for name in api.public_names(module):
            value = getattr(module, name)
            if inspect.isclass(value) and issubclass(value, Exception):
                found.add(value)
    return found


ERRORS = tuple(sorted(public_errors(), key=lambda error: error.__name__))

# The built-in types that callers caught before the hierarchy existed.
BUILT_IN = {
    errors.MissingReferenceError: LookupError,
    errors.AmbiguousReferenceError: LookupError,
    errors.UnknownExtensionError: LookupError,
    errors.ReferenceTypeError: TypeError,
    errors.PublishedFileError: OSError,
    errors.BackendUnavailableError: RuntimeError,
    errors.AttemptDeadlineError: RuntimeError,
    RangekeeperError: Exception,
}

# ADR-016 and later decisions name this error; jsonschema has one too.
SHARED_NAMES = {"ValidationError"}


def defined_exceptions():
    """Yield each Exception class that a rangekeeper module defines."""
    for info in pkgutil.walk_packages(rangekeeper.__path__, "rangekeeper."):
        module = importlib.import_module(info.name)
        for value in vars(module).values():
            if (
                inspect.isclass(value)
                and issubclass(value, Exception)
                and value.__module__ == module.__name__
            ):
                yield value


def test_every_defined_error_is_public():
    assert set(defined_exceptions()) <= set(ERRORS)
    assert {getattr(errors, name) for name in errors.__all__ if name != "Code"} <= set(
        ERRORS
    )


@pytest.mark.parametrize("error", ERRORS, ids=lambda error: error.__name__)
def test_each_error_subclasses_the_base_and_ends_in_error(error):
    assert issubclass(error, RangekeeperError)
    assert error.__name__.endswith("Error")
    assert issubclass(error, BUILT_IN.get(error, ValueError))


@pytest.mark.parametrize(
    "error",
    [error for error in ERRORS if "code" in vars(error)],
    ids=lambda error: error.__name__,
)
def test_class_codes_are_codes(error):
    assert isinstance(error.code, Code)


def test_instance_codes_are_codes():
    report = ValidationReport((Issue(Code.UNIQUE, "duplicate"),))
    assert errors.ValidationError(report).code is Code.UNIQUE
    assert errors.ContractError("text").code is Code.CONTRACT
    assert errors.UnsupportedError("text").code is Code.UNSUPPORTED_CAPABILITY
    assert (
        errors.UnsupportedError("text", code="symbol_limit").code is Code.SYMBOL_LIMIT
    )
    hierarchy = HierarchyError("hierarchy.cycle", "text", ids=(uuid4(),))
    assert hierarchy.code is Code.HIERARCHY_CYCLE
    # Every other error has a class code.
    assert all(
        isinstance(getattr(error, "code", None), Code)
        for error in ERRORS
        if error
        not in {
            RangekeeperError,
            errors.ValidationError,
            errors.ContractError,
            errors.UnsupportedError,
            HierarchyError,
        }
    )


def test_error_names_do_not_clash_with_dependency_errors():
    modules = ["jsonschema", "jsonschema.exceptions", "pint", "pint.errors", "moneyed"]
    modules += ["polars", "polars.exceptions", "pyarrow", "duckdb", "numpy"]
    modules += ["scipy", "pyomo.common.errors", "highspy", "yaml"]
    names = {error.__name__ for error in ERRORS}
    for name in modules:
        module = importlib.import_module(name)
        theirs = {
            key
            for key, value in vars(module).items()
            if inspect.isclass(value) and issubclass(value, BaseException)
        }
        assert names & theirs <= SHARED_NAMES, name
