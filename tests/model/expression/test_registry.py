"""The equation-function registry declares each function once (ADR-015, D32)."""

import subprocess
import sys
from pathlib import Path

import pytest

import rangekeeper.expressions as rx
from rangekeeper.errors import Code, ContractError
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.functions import (
    EquationFunction,
    EquationFunctions,
    Form,
)
from rangekeeper.schema.enums import ParameterKind
from rangekeeper.schema.records import Function

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "tools/expressions/generate.py"


def test_the_generated_files_match_the_registry():
    """rx, the Flow methods and the docs table are written from the registry.

    The check needs the source tree; the tests of an installed wheel have none.
    """
    if not GENERATOR.exists():
        pytest.skip("the generated files are checked in the source tree")
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("function", list(functions), ids=lambda f: f.code)
def test_each_function_has_one_stable_function_record(function: EquationFunction):
    record = function.record()
    assert isinstance(record, Function)
    assert (record.id, record.code, record.version) == (
        function.id,
        function.code,
        "1",
    )
    assert record == function.record()
    assert functions.get(function.id) is function
    assert function.mirrors in record.semantics
    assert Function.from_data(record.to_data()) == record


@pytest.mark.parametrize("function", list(functions), ids=lambda f: f.code)
def test_parameters_that_take_a_position_come_first(function: EquationFunction):
    kinds = [parameter.call for parameter in function.parameters]
    named = (
        kinds.index(ParameterKind.NAMED_ONLY)
        if ParameterKind.NAMED_ONLY in kinds
        else len(kinds)
    )
    assert all(kind is ParameterKind.NAMED_ONLY for kind in kinds[named:])
    if function.form is Form.METHOD:
        assert function.parameters[0].name == "flow"
        assert function.parameters[0].call is ParameterKind.POSITIONAL_OR_NAMED


def test_each_function_is_in_rx_and_each_method_on_handles():
    for function in functions:
        if function.form is Form.FUNCTION:
            namespace, _, name = function.name.rpartition(".")
            module = getattr(rx, namespace) if namespace else rx
            assert callable(getattr(module, name)), function.code
        else:
            assert callable(getattr(rx.Term, function.name)), function.code


def test_a_lookup_suggests_the_nearest_names():
    assert functions.function(name="max").code == "rx.max"
    assert functions.method(name="at").code == "Flow.at"
    with pytest.raises(ContractError) as error:
        functions.function(name="mux")
    assert error.value.code is Code.EQUATION_FUNCTION
    assert error.value.values["suggestions"] == ["rx.max"]
    with pytest.raises(ContractError) as error:
        functions.method(name="totl")
    assert error.value.values["suggestions"] == ["total"]


def test_a_code_is_registered_once():
    registry = EquationFunctions()
    registry.register(functions.function(name="max"))
    with pytest.raises(ContractError) as error:
        registry.register(functions.function(name="max"))
    assert error.value.code is Code.EXTENSION_CONFLICT
    with pytest.raises(TypeError):
        registry.register("max")  # type: ignore[arg-type]
