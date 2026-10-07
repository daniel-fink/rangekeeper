"""Explicit workflow wiring for native Excel operations.

Direct Excel APIs do not import this module. Only the workflow catalog selects it.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from rangekeeper.workflow._contracts import (
    OperationDeclaration,
    Produced,
    SourceCheckDeclaration,
)
from rangekeeper.workflow._declarations import sequence, text
from rangekeeper.workflow._schema import obj
from rangekeeper.evidence import fingerprint
from rangekeeper.workflow.sources import resolve_file

from . import ExtractionSpec, extract_table, read
from .classification import RowClassificationSpec, classify_rows


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadSpec:
    """Binds a logical source to allowed filenames and an expected edition, keeping
    filesystem choices out of graph identity.
    """

    files: tuple[str, ...]
    source_key: str
    checksum: str | None = None

    def __post_init__(self):
        paths = sequence(self.files)
        if not paths:
            raise ValueError("read requires file candidates")
        for p in paths:
            text(p)
            if Path(p).is_absolute() or ".." in Path(p).parts:
                raise ValueError("Input paths must stay under input_root")
        text(self.source_key)
        if self.checksum is not None:
            text(self.checksum)
        object.__setattr__(self, "files", paths)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractSpec:
    """Connects a prior workbook output to an existing ExtractionSpec; the wrapper
    supplies workflow wiring rather than another extraction algorithm.
    """

    input: str
    specification: ExtractionSpec
    unique_stop: bool = False

    def __post_init__(self):
        text(self.input)
        if not isinstance(self.specification, ExtractionSpec):
            raise TypeError("Expected ExtractionSpec")
        if type(self.unique_stop) is not bool:
            raise TypeError("unique_stop must be boolean")
        if self.unique_stop and self.specification.rows.stop_before is None:
            raise ValueError("unique_stop requires a stopping marker")

    @classmethod
    def from_mapping(cls, data):
        return cls(
            **{
                **data,
                "specification": ExtractionSpec.from_mapping(data["specification"]),
            }
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ClassifySpec:
    """Supplies both extracted Evidence and its native snapshot because physical
    occupancy cannot be inferred from interpreted values alone.
    """

    input: str
    workbook: str
    specification: RowClassificationSpec

    def __post_init__(self):
        text(self.input)
        text(self.workbook)
        if not isinstance(self.specification, RowClassificationSpec):
            raise TypeError("Expected RowClassificationSpec")

    @classmethod
    def from_mapping(cls, data):
        return cls(
            **{
                **data,
                "specification": RowClassificationSpec.from_mapping(
                    data["specification"]
                ),
            }
        )


def request_properties():
    string = {"type": "string", "minLength": 1}
    names = {"type": "array", "items": string}
    boolean = {"type": "boolean"}
    comparison = {"enum": ["exact", "trim"]}
    rows = obj(
        {
            "start": {"type": "integer", "minimum": 1},
            "end": {"type": "integer", "minimum": 1},
            "stop_before": obj(
                {"column": string, "equals": {}, "comparison": comparison},
                ("column", "equals"),
            ),
        },
        ("start",),
    )
    rows["oneOf"] = [{"required": ["end"]}, {"required": ["stop_before"]}]
    extraction = obj(
        {
            "id": string,
            "version": {"const": 1},
            "sheet": string,
            "rows": rows,
            "columns": {
                "type": "array",
                "minItems": 1,
                "items": obj({"name": string, "column": string}, ("name", "column")),
            },
            "expect": obj({"cells": {"type": "object"}, "comparison": comparison}),
            "formula_values": {"const": "cached"},
        },
        ("id", "version", "sheet", "rows", "columns"),
    )
    properties = {
        "read": {
            "files": {**names, "minItems": 1},
            "source_key": string,
            "checksum": {"type": ["string", "null"]},
        },
        "extract": {
            "input": string,
            "specification": extraction,
            "unique_stop": boolean,
        },
        "classify_rows": {
            "input": string,
            "workbook": string,
            "specification": obj(
                {
                    "identifier": string,
                    "pattern": string,
                    "output": string,
                    "columns": names,
                },
                ("identifier", "pattern"),
            ),
        },
    }
    return properties


def inspect_input(request, root):
    """Read bytes and declared edition only; never recalculate or modify a workbook."""
    from rangekeeper.operation import _Failure

    try:
        path = resolve_file(root, request.files, request.source_key)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = (
            request.checksum.removeprefix("sha256:").lower()
            if request.checksum
            else None
        )
        return {
            "name": request.source_key,
            "path": str(path.resolve()),
            "checksum": checksum,
            "expected_checksum": expected,
            "status": "ready" if expected is None or expected == checksum else "error",
            "message": (
                ""
                if expected is None or expected == checksum
                else "Source checksum differs from declared edition"
            ),
        }
    except (_Failure, OSError) as exc:
        return {
            "name": request.source_key,
            "path": None,
            "checksum": None,
            "expected_checksum": request.checksum,
            "status": "error",
            "message": str(exc),
        }


def _read(request, inputs, context):
    path = resolve_file(context.input_root, request.files, request.source_key)
    return read(
        path,
        namespace=context.namespace,
        source_key=request.source_key,
        name=request.source_key,
        expected_checksum=request.checksum,
    )


def _extract(request, inputs, context):
    return extract_table(
        inputs[request.input], request.specification, unique_stop=request.unique_stop
    )


def _classify(request, inputs, context):
    return classify_rows(
        inputs[request.input],
        inputs[request.workbook],
        specification=request.specification,
        settings=context.settings,
        name=context.name,
    )


def describe_book(value):
    return Produced(value, value.fingerprint, value.source)


def describe_table(value):
    return Produced(value, fingerprint(value))


MODULES = ("adapters/excel/",)
OPERATIONS = {
    "read": OperationDeclaration(
        ReadSpec,
        _read,
        describe_book,
        lambda: request_properties()["read"],
        output="workbook",
        modules=MODULES,
        dependencies_used=("openpyxl",),
        inspect_input=inspect_input,
    ),
    "extract": OperationDeclaration(
        ExtractSpec,
        _extract,
        describe_table,
        lambda: request_properties()["extract"],
        inputs=(("input", "workbook"),),
        modules=MODULES,
    ),
    "classify_rows": OperationDeclaration(
        ClassifySpec,
        _classify,
        describe_table,
        lambda: request_properties()["classify_rows"],
        inputs=(("input", "table"), ("workbook", "workbook")),
        modules=MODULES,
    ),
}


def format_reference(location):
    """Recognize this adapter's native address; leave other locations untouched."""
    if set(location.reference) != {"sheet", "cell"}:
        return None
    return f"{location.source.name} · {location.reference['sheet']}!{location.reference['cell']}"


def record_reference(location):
    if set(location.reference) != {"sheet", "cell"}:
        return None
    from ._coordinates import address

    row, _ = address(location.reference["cell"])
    return f"{location.source.checksum}:{location.reference['sheet']}:{row}"


def _health(spec, inputs):
    from rangekeeper.workflow.source_checks import SourceCheck

    from .inspection import health

    book = inputs[spec["workbook"]]
    return tuple(
        SourceCheck(
            spec["id"] + "-" + item.code,
            book.source.name + ": " + item.name,
            "finding" if item.cells else "passed",
            len(item.cells),
            item.explanation,
            tuple(format_reference(c.location) for c in item.cells),
        )
        for item in health(book)
    )


SOURCE_CHECKS = {
    "workbook_health": SourceCheckDeclaration(
        (("workbook", "workbook"),), _health, modules=MODULES
    ),
}
