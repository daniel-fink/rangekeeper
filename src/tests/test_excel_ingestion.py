"""XLSX fidelity, declarations, provenance and deterministic extraction."""

import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import time
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from rangekeeper.graph.adapter import document, excel
from rangekeeper.graph.adapter.errors import AdapterEncodingError
from rangekeeper.graph.adapter.ingestion import fingerprint, tabular
from rangekeeper.graph.provenance import ClaimKind, Location

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def declaration(**overrides):
    supplied = {
        "id": "apartments",
        "version": 1,
        "sheet": "Unit Pricing",
        "expect": {"comparison": "trim", "cells": {"A7": "Unit No", "J7": "M²"}},
        "rows": {
            "start": 8,
            "stop_before": {
                "column": "A",
                "equals": "Assumptions:",
                "comparison": "trim",
            },
        },
        "columns": [
            {"name": "unit", "column": "A"},
            {"name": "floor", "column": "B"},
            {"name": "parking", "column": "G"},
            {"name": "area", "column": "J"},
        ],
    }
    supplied.update(overrides)
    return excel.ExtractionSpec.from_mapping(supplied)


def read(path, **kwargs):
    return excel.read(
        path, namespace=NAMESPACE_URL, source_key="jll", name="JLL", **kwargs
    )


@pytest.fixture
def workbook_path(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "source.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Unit Pricing"
    sheet["A7"], sheet["B7"], sheet["J7"] = "Unit No", "Floor", "M² "
    sheet["A8"], sheet["B8"], sheet["J8"] = "04.01", 4, 103
    sheet["A10"] = " Assumptions: "
    sheet["A12"] = "=1+1"  # absent numeric cache
    sheet["A13"] = "=1+1"  # populated numeric cache
    sheet["A14"] = '=IF(TRUE,"","")'  # explicitly stored empty string cache
    sheet["A15"] = "#DIV/0!"
    sheet["A16"] = ""
    sheet["A17"], sheet["A17"].number_format = 0.5, "h:mm"
    sheet["A18"] = '<script>alert("source")</script>'
    sheet["A19"] = "=1/0"  # cached error
    sheet["A20"] = "x" * 3000
    sheet.merge_cells("A22:B22")
    sheet["A22"] = "Merged heading"
    hidden = book.create_sheet("Hidden")
    hidden.sheet_state = "hidden"
    hidden["A1"] = "retained"
    book.save(path)
    book.close()
    with ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    xml = ET.fromstring(members["xl/worksheets/sheet1.xml"])
    for coordinate, value, kind in (
        ("A13", "2", "n"),
        ("A14", None, "str"),
        ("A19", "#DIV/0!", "e"),
    ):
        cell = xml.find(f'.//s:c[@r="{coordinate}"]', NS)
        cell.set("t", kind)
        cell.find("s:v", NS).text = value
    members["xl/worksheets/sheet1.xml"] = ET.tostring(xml)
    with ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def test_snapshot_fidelity_and_no_source_mutation(workbook_path):
    before = workbook_path.read_bytes()
    outcome = read(workbook_path)
    assert outcome.diagnostics == ()
    book = outcome.output
    assert book.source.checksum == sha256(before).hexdigest()
    sheet = book.sheet("Unit Pricing")
    assert sheet.cell("A8").raw == "04.01"
    assert sheet.cell("A12").formula == "=1+1"
    assert sheet.cell("A12").cache_present is False
    assert sheet.cell("A13").cached == 2
    assert sheet.cell("A13").xml_formula == "1+1"
    assert sheet.cell("A14").cache_present is True
    assert sheet.cell("A14").value == ""
    assert sheet.cell("A15").data_type == "e"
    assert sheet.cell("A16").value == ""
    assert sheet.cell("A17").value == time(12)
    assert sheet.cell("A17").xml_value == "0.5"
    assert sheet.cell("B22").value is None
    assert sheet.cell("B22").merged_anchor == "A22"
    assert sheet.cell("Z99").raw is None
    assert book.sheet("Hidden").state == "hidden"
    assert all(cell.location.source is book.source for cell in sheet.cells.values())
    assert workbook_path.read_bytes() == before
    with pytest.raises(TypeError):
        sheet.cells["A8"] = sheet.cell("A13")
    with pytest.raises(FrozenInstanceError):
        sheet.cell("A8").raw = "changed"
    with pytest.raises(KeyError):
        book.sheet("missing")


def test_physical_extraction_keeps_blank_rows_and_issues(workbook_path):
    book = read(workbook_path).output
    outcome = excel.extract_table(book, declaration())
    assert outcome.diagnostics == ()
    evidence = outcome.output
    assert evidence.data.columns == ("unit", "floor", "parking", "area")
    assert len(evidence.data.rows) == 2  # physical blank row 9 is preserved
    first = evidence.data.rows[0]
    assert dict(first.values) == {
        "unit": "04.01",
        "floor": 4,
        "parking": None,
        "area": 103,
    }
    assert all(value is None for value in evidence.data.rows[1].values.values())
    claim = tabular.claim(evidence, first.id, "area")
    assert claim.kind is ClaimKind.SOURCED
    assert claim.sources[0].source is book.source
    assert dict(claim.sources[0].reference) == {"sheet": "Unit Pricing", "cell": "J8"}
    assert tabular.issues_for(evidence, first.id, "parking")[0].code == "blank_cell"
    assert outcome.operation.specification["formula_values"] == "cached"


def test_formula_lineage_and_distinct_missing_states(workbook_path):
    book = read(workbook_path).output
    spec = declaration(
        rows={"start": 12, "end": 22},
        columns=[{"name": "value", "column": "A"}, {"name": "covered", "column": "B"}],
    )
    evidence = excel.extract_table(book, spec).output
    claims = [tabular.claim(evidence, row.id, "value") for row in evidence.data.rows]
    assert claims[0].value is None
    assert claims[1].value == 2
    assert claims[2].value == ""
    assert claims[3].value is None
    assert claims[4].value == ""
    assert claims[5].value == time(12)
    assert claims[6].value == '<script>alert("source")</script>'
    assert claims[7].value is None
    assert claims[1].kind is ClaimKind.DERIVED
    observed = dict(claims[1].sources[0].value)
    assert observed["formula"] == "=1+1" and observed["cached"] == 2
    assert claims[1].sources[0].sources[0].source is book.source
    assert (
        tabular.issues_for(evidence, evidence.data.rows[0].id, "value")[0].code
        == "missing_formula_cache"
    )
    assert (
        tabular.issues_for(evidence, evidence.data.rows[3].id, "value")[0].code
        == "excel_error"
    )
    assert tabular.issues_for(evidence, evidence.data.rows[2].id, "value") == ()
    assert (
        tabular.issues_for(evidence, evidence.data.rows[-1].id, "covered")[0].code
        == "merged_cell_covered"
    )


def test_identities_repeated_reads_paths_columns_and_source_editions(
    workbook_path, tmp_path
):
    first_book = read(workbook_path).output
    first = excel.extract_table(first_book, declaration()).output
    copied = tmp_path / "other.xlsx"
    copied.write_bytes(workbook_path.read_bytes())
    second_book = read(copied).output
    second = excel.extract_table(second_book, declaration()).output
    assert first_book.fingerprint == second_book.fingerprint
    assert fingerprint(first) == fingerprint(second)
    assert [i.id for i in first.issues] == [i.id for i in second.issues]
    spec = declaration(columns=list(reversed(declaration().to_mapping()["columns"])))
    reordered = excel.extract_table(first_book, spec).output
    assert [r.id for r in first.data.rows] == [r.id for r in reordered.data.rows]
    assert fingerprint(first) != fingerprint(reordered)
    # One source cell mapped twice must share a canonical Claim, not duplicate its ID.
    repeated = excel.extract_table(
        first_book,
        declaration(
            columns=[{"name": "a", "column": "J"}, {"name": "b", "column": "J"}]
        ),
    ).output
    row = repeated.data.rows[0]
    assert tabular.claim(repeated, row.id, "a") is tabular.claim(repeated, row.id, "b")
    openpyxl = pytest.importorskip("openpyxl")
    changed = openpyxl.load_workbook(copied)
    changed["Unit Pricing"]["J8"] = 104
    changed.save(copied)
    changed.close()
    changed_book = read(copied).output
    assert changed_book.source.id != first_book.source.id
    assert changed_book.fingerprint != first_book.fingerprint


def test_snapshot_fingerprint_includes_observations(workbook_path):
    book = read(workbook_path).output
    sheet = book.worksheets[0]
    changed_cells = dict(sheet.cells)
    changed_cells["J8"] = replace(changed_cells["J8"], raw=999)
    changed = replace(
        book, worksheets=(replace(sheet, cells=changed_cells), *book.worksheets[1:])
    )
    assert changed.fingerprint != book.fingerprint


def test_source_failures_have_diagnostics_without_fabricated_sources(
    tmp_path, workbook_path
):
    missing = read(tmp_path / "missing.xlsx")
    assert missing.output is None
    assert missing.operation.inputs["source"] is None
    assert missing.diagnostics[0].code == "source_unavailable"
    assert missing.diagnostics[0].locations == ()
    mismatch = read(workbook_path, expected_checksum="0" * 64)
    assert mismatch.output is None
    assert mismatch.diagnostics[0].code == "checksum_mismatch"
    assert mismatch.diagnostics[0].locations[0].source.checksum != "0" * 64
    corrupt = tmp_path / "corrupt.xlsx"
    corrupt.write_bytes(b"not a zip")
    assert read(corrupt).diagnostics[0].code == "invalid_workbook"
    assert read(tmp_path / "source.csv").diagnostics[0].code == "unsupported_format"


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"sheet": "missing"}, "missing_sheet"),
        ({"expect": {"cells": {"A7": "different"}}}, "layout_mismatch"),
        (
            {"rows": {"start": 8, "stop_before": {"column": "A", "equals": "missing"}}},
            "missing_stop_marker",
        ),
    ],
)
def test_extraction_mismatch_diagnostics(workbook_path, changes, code):
    book = read(workbook_path).output
    outcome = excel.extract_table(book, declaration(**changes))
    assert outcome.output is None
    assert outcome.diagnostics[0].code == code
    assert outcome.diagnostics[0].locations[0].source is book.source
    if code == "missing_sheet":
        assert dict(outcome.diagnostics[0].locations[0].reference) == {}


def test_empty_range_and_exact_typed_guards(workbook_path):
    book = read(workbook_path).output
    empty = excel.extract_table(
        book,
        declaration(
            rows={
                "start": 10,
                "stop_before": {
                    "column": "A",
                    "equals": "Assumptions:",
                    "comparison": "trim",
                },
            }
        ),
    )
    assert empty.output.data.rows == ()
    assert empty.output.claims == {}
    mismatch = excel.extract_table(book, declaration(expect={"cells": {"B8": 4.0}}))
    assert mismatch.diagnostics[0].code == "layout_mismatch"
    exact = excel.extract_table(book, declaration(expect={"cells": {"J7": "M²"}}))
    assert exact.diagnostics[0].code == "layout_mismatch"


def test_navigation_inspection_truncation_and_literal_search(workbook_path):
    book = read(workbook_path).output
    page = document.children(book, limit=1).output
    assert page.items[0].label == "Unit Pricing"
    assert (
        document.children(book, limit=1, cursor=page.next_cursor).output.items[0].label
        == "Hidden"
    )
    cells = document.children(book, page.items[0].location, limit=1).output
    assert dict(cells.items[0].location.reference) == {
        "sheet": "Unit Pricing",
        "cell": "A7",
    }
    selected = Location(
        source=book.source, reference={"sheet": "Unit Pricing", "cell": "A20"}
    )
    preview = document.inspect(book, selected).output
    assert preview.truncated is True
    assert len(preview.content.raw) == 2000
    assert len(book.sheet("Unit Pricing").cell("A20").raw) == 3000
    assert (
        document.search(book, "04.01").output.items[0].location.reference["cell"]
        == "A8"
    )
    assert document.search(book, "=1+1").output.items == ()
    assert document.search(book, "unit no").output.items == ()
    assert document.search(book, "unit no", case_sensitive=False).output.items
    assert (
        document.search(book, "<script>").output.items[0].label.startswith("<script>")
    )
    assert document.children(book, selected).output.items == ()
    bad = Location(source=book.source, reference={"page": "1"})
    assert document.inspect(book, bad).diagnostics[0].code == "invalid_location"


@pytest.mark.parametrize(
    "changes",
    [
        {"version": True},
        {"version": 2},
        {"rows": {"start": 8}},
        {"rows": {"start": 8, "end": 7}},
        {"columns": []},
        {
            "rows": {
                "start": 8,
                "end": 9,
                "stop_before": {"column": "A", "equals": "end"},
            }
        },
        {"formula_values": "calculate"},
        {"unknown": 1},
        {"columns": {"unit": "A"}},
        {"columns": [{"name": "x", "column": "XFE"}]},
        {"columns": [{"name": "x", "column": "A"}, {"name": "x", "column": "B"}]},
    ],
)
def test_invalid_declarations_raise(changes):
    with pytest.raises((TypeError, ValueError)):
        declaration(**changes)


def test_yaml_decoder_defaults_order_and_rejections():
    pytest.importorskip("yaml")
    text = """
id: example
version: 1
sheet: Sheet
rows: {start: 1, end: 2}
columns:
  - {name: a, column: A}
  - {name: b, column: B}
"""
    spec = excel.load_specification(text)
    assert spec.formula_values == "cached"
    assert spec.expect.comparison == "exact"
    assert [column.name for column in spec.columns] == ["a", "b"]
    assert excel.ExtractionSpec.from_mapping(spec.to_mapping()) == spec
    for invalid in (
        text + "id: duplicate\n",
        text.replace("start: 1", "start: 1, start: 2"),
        "!!python/object/apply:os.system ['echo wrong']",
    ):
        with pytest.raises(AdapterEncodingError):
            excel.load_specification(invalid)


def test_fresh_process_determinism_and_optional_import_isolation(workbook_path):
    # These subprocesses run only when this test is explicitly executed.
    program = """
import sys
from uuid import NAMESPACE_URL
from rangekeeper.graph.adapter import excel
from rangekeeper.graph.adapter.ingestion import fingerprint
book = excel.read(sys.argv[1], namespace=NAMESPACE_URL, source_key="jll", name="JLL").output
spec = excel.ExtractionSpec(id="one", version=1, sheet="Unit Pricing", rows=excel.Rows(start=8,end=8), columns=(excel.Column(name="unit",column="A"),))
print(fingerprint(excel.extract_table(book,spec).output))
"""
    command = [sys.executable, "-c", program, str(workbook_path)]
    assert subprocess.check_output(command) == subprocess.check_output(command)
    isolated = """
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split(".")[0] in {"openpyxl", "yaml"}:
        raise AssertionError("optional dependency eagerly imported")
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from rangekeeper.graph.adapter import document, operation, excel
assert excel.ExtractionSpec
"""
    subprocess.run([sys.executable, "-c", isolated], check=True)


def test_reader_uses_one_captured_byte_sequence(workbook_path, monkeypatch):
    from rangekeeper.graph.adapter.excel import reader

    original = workbook_path.read_bytes()
    real_parse = reader._parse
    reads = []
    original_read_bytes = Path.read_bytes

    def counted(path):
        reads.append(path)
        return original_read_bytes(path)

    def replace_live_file(data, source, operation):
        # Only a temporary fixture changes. The captured source remains readable.
        workbook_path.write_bytes(b"a different live edition")
        return real_parse(data, source, operation)

    monkeypatch.setattr(Path, "read_bytes", counted)
    monkeypatch.setattr(reader, "_parse", replace_live_file)
    outcome = read(workbook_path)
    assert reads == [workbook_path]
    assert outcome.output.source.checksum == sha256(original).hexdigest()
    assert outcome.output.sheet("Unit Pricing").cell("J8").value == 103


def test_missing_optional_reader_dependency_is_explicit(workbook_path, monkeypatch):
    from importlib.metadata import PackageNotFoundError

    from rangekeeper.graph.adapter.excel import reader

    def unavailable(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(reader, "version", unavailable)
    outcome = read(workbook_path)
    assert outcome.output is None
    assert outcome.diagnostics[0].code == "dependency_unavailable"
    assert outcome.operation.specification["parser"]["version"] is None
    assert outcome.diagnostics[0].locations[0].source.checksum


def test_canonical_coordinates_and_single_cell_merge(workbook_path):
    from rangekeeper.graph.adapter.excel._coordinates import address

    assert address("XFD1048576") == (1048576, 16384)
    for coordinate in ("a1", "$A$1", "A0", "A01", "XFE1", "A1048577", "A1:B2"):
        with pytest.raises(ValueError):
            address(coordinate)
    book = read(workbook_path).output
    sheet = replace(book.worksheets[0], merged_ranges=("A8",))
    assert sheet.cell("A8").merged_anchor == "A8"
    assert sheet.cell("A8").value == "04.01"


def test_missing_inspection_sheet_uses_actual_workbook_root(workbook_path):
    book = read(workbook_path).output
    outcome = document.inspect(
        book, Location(source=book.source, reference={"sheet": "missing"})
    )
    diagnostic = outcome.diagnostics[0]
    assert outcome.output is None
    assert diagnostic.code == "missing_sheet"
    assert dict(diagnostic.locations[0].reference) == {}
    assert diagnostic.details["available_sheets"] == ("Unit Pricing", "Hidden")


def test_resolved_defaults_and_yaml_mapping_order_have_identical_operations(
    workbook_path,
):
    from rangekeeper.graph.adapter.operation import fingerprint as operation_fingerprint

    book = read(workbook_path).output
    implicit = declaration()
    explicit = declaration(formula_values="cached")
    assert operation_fingerprint(
        excel.extract_table(book, implicit).operation
    ) == operation_fingerprint(excel.extract_table(book, explicit).operation)
    reordered = dict(reversed(tuple(implicit.to_mapping().items())))
    same = excel.ExtractionSpec.from_mapping(reordered)
    assert fingerprint(excel.extract_table(book, same).output) == fingerprint(
        excel.extract_table(book, implicit).output
    )


def test_snapshot_construction_defects_propagate(workbook_path, monkeypatch):
    from rangekeeper.graph.adapter.excel import reader

    def broken_cell(*args, **kwargs):
        raise ValueError("snapshot construction defect")

    monkeypatch.setattr(reader, "Cell", broken_cell)
    with pytest.raises(ValueError, match="snapshot construction defect"):
        read(workbook_path)


def test_inspection_and_extraction_share_missing_sheet_diagnostics(workbook_path):
    book = read(workbook_path).output
    inspected = document.inspect(
        book,
        Location(source=book.source, reference={"sheet": "missing"}),
    )
    extracted = excel.extract_table(book, declaration(sheet="missing"))
    assert inspected.diagnostics == extracted.diagnostics
