"""The error hierarchy of ``rangekeeper.errors`` (ADR-016)."""

import importlib
import inspect
import pickle
import pkgutil
from pathlib import Path
from uuid import uuid4

import pytest

import rangekeeper
from rangekeeper import errors
from rangekeeper.errors import Code, RangekeeperError
from rangekeeper.execution import OutcomeError, Status
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
    defined = {error for error in defined_exceptions() if error.__name__[0] != "_"}
    assert defined <= set(ERRORS)
    exported = {getattr(errors, name) for name in errors.__all__}
    assert {item for item in exported if inspect.isclass(item)} - {
        Code,
        errors.ErrorFields,
    } <= set(ERRORS)


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
    hierarchy = HierarchyError("text", code="hierarchy.cycle", targets=(uuid4(),))
    assert hierarchy.code is Code.HIERARCHY_CYCLE
    # Every other error has a class code.
    assert all(
        isinstance(getattr(error, "code", None), Code)
        for error in ERRORS
        if error not in {RangekeeperError, errors.ValidationError, HierarchyError}
    )


def test_an_error_without_a_class_code_takes_one():
    with pytest.raises(TypeError, match="code"):
        HierarchyError("text")


# The keywords that some errors need besides the common fields.
REQUIRED = {
    errors.PublishedFileError: {"file": Path("published.json")},
    errors.EquationError: {"text": "a = b c", "start": 6, "end": 7},
    OutcomeError: {"status": Status.INFEASIBLE, "equation": "a >= b"},
}


def made(error):
    """Return an instance of an error class with every common field set."""
    first = uuid4() if issubclass(error, errors.MissingReferenceError) else "text"
    if issubclass(error, errors.AmbiguousReferenceError):
        first = "building_c"
    return error(
        first,
        code=Code.CONTRACT,
        document_id=uuid4(),
        path="/values/0",
        targets=(uuid4(), uuid4()),
        **REQUIRED.get(error, {}),
    )


@pytest.mark.parametrize(
    "error",
    [error for error in ERRORS if error is not errors.ValidationError],
    ids=lambda error: error.__name__,
)
def test_each_error_takes_the_common_fields_by_keyword(error):
    instance = made(error)
    assert instance.code is Code.CONTRACT
    assert instance.path == "/values/0"
    assert len(instance.targets) == 2
    assert instance.document_id is not None


@pytest.mark.parametrize("error", ERRORS, ids=lambda error: error.__name__)
def test_each_error_keeps_its_fields_through_pickle(error):
    if error is errors.ValidationError:
        instance = error(ValidationReport((Issue(Code.UNIQUE, "duplicate"),)))
    else:
        instance = made(error)
    copy = pickle.loads(pickle.dumps(instance))
    assert type(copy) is error
    assert str(copy) == str(instance)
    assert copy._fields() == instance._fields()
    assert copy.code is instance.code


def test_the_common_fields_are_the_keywords_of_the_base():
    keywords = inspect.signature(RangekeeperError).parameters
    assert set(errors.ErrorFields.__annotations__) == set(keywords) - {"message"}


def test_unsupported_error_keeps_its_fields_through_pickle():
    target = uuid4()
    error = errors.UnsupportedError(
        "text",
        code=Code.NONAFFINE_UNKNOWNS,
        targets=(target,),
        equation="noi = coverage * debt_service",
        unknowns=["coverage", "debt_service"],
    )
    copy = pickle.loads(pickle.dumps(error))
    assert (str(copy), copy.code, copy.targets, copy.equation, copy.unknowns) == (
        "text",
        Code.NONAFFINE_UNKNOWNS,
        (target,),
        "noi = coverage * debt_service",
        ("coverage", "debt_service"),
    )


def test_equation_error_marks_the_part_that_fails_and_keeps_it_through_pickle():
    error = errors.EquationError(
        "unexpected 'c'",
        text="a = b c",
        start=6,
        end=7,
        suggestions=["*"],
    )
    assert error.code is Code.EQUATION_SYNTAX
    assert str(error) == "unexpected 'c'\n  a = b c\n        ^"
    copy = pickle.loads(pickle.dumps(error))
    assert (str(copy), copy.code, copy.start, copy.end, copy.suggestions) == (
        str(error),
        Code.EQUATION_SYNTAX,
        6,
        7,
        ("*",),
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
