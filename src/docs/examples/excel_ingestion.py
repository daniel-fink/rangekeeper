"""Executable extraction companion for synthetic and checksum-bound local sources.

Default: create an isolated synthetic workbook in a temporary directory.
Optional: --workbook PATH --checksum HEX reads a pinned local JLL edition.
Neither mode modifies source files or regenerates Mandarin artifacts.
"""

import argparse
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypeVar
from uuid import NAMESPACE_URL

from rangekeeper.graph.adapter import document, excel, operation
from rangekeeper.graph.adapter.ingestion import fingerprint, tabular
from rangekeeper.graph.adapter.operation import Outcome
from rangekeeper.graph.provenance import Location

T = TypeVar("T")


def require(outcome: Outcome[T]) -> T:
    print(
        "Operation:",
        outcome.operation.method.code,
        operation.fingerprint(outcome.operation),
    )
    for diagnostic in outcome.diagnostics:
        print(diagnostic.code, diagnostic.message, dict(diagnostic.details))
    if outcome.output is None:
        raise RuntimeError(
            "The operation produced no output; review the diagnostics above"
        )
    return outcome.output


def synthetic(path: Path) -> None:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Unit Pricing"
    sheet["A7"], sheet["B7"], sheet["J7"] = "Unit No", "Floor", "M² "
    sheet["A8"], sheet["B8"], sheet["J8"] = "04.01", 4, 103
    sheet["A10"] = "Assumptions:"
    book.save(path)
    book.close()


def review(path: Path, checksum: str, specification_path: Path) -> None:
    def read():
        return excel.read(
            path,
            namespace=NAMESPACE_URL,
            source_key="jll-example",
            name="JLL example",
            expected_checksum=checksum,
        )

    workbook = require(read())
    description = require(document.describe(workbook))
    print("Document:", description.format, dict(description.metadata))
    print(
        "Worksheets:",
        [item.label for item in require(document.children(workbook)).items],
    )
    observed = require(
        document.inspect(
            workbook,
            Location(
                source=workbook.source,
                reference={"sheet": "Unit Pricing", "cell": "J8"},
            ),
        )
    )
    print("J8 observation:", observed.content)
    specification = excel.load_specification(
        specification_path.read_text(encoding="utf-8")
    )
    evidence = require(excel.extract_table(workbook, specification))
    first = evidence.data.rows[0]
    assert first.id is not None
    print("First row:", dict(first.values))
    print("Physical rows:", len(evidence.data.rows))
    print("Area Claim:", tabular.claim(evidence, first.id, "area"))
    print("Parking issues:", tabular.issues_for(evidence, first.id, "parking"))
    assert dict(first.values) == {
        "unit": "04.01",
        "floor": 4,
        "parking": None,
        "area": 103,
    }
    repeated = require(excel.extract_table(require(read()), specification))
    assert fingerprint(evidence) == fingerprint(repeated)
    assert [issue.id for issue in evidence.issues] == [
        issue.id for issue in repeated.issues
    ]
    print("Evidence fingerprint:", fingerprint(evidence))
    print("Repeat extraction: identical Evidence fingerprint and issue IDs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path)
    parser.add_argument("--checksum", help="Expected SHA-256 of the local JLL workbook")
    parser.add_argument(
        "--specification", type=Path, default=Path(__file__).with_suffix(".yaml")
    )
    args = parser.parse_args()
    if args.workbook is not None:
        if args.checksum is None:
            parser.error("--workbook requires --checksum")
        review(args.workbook, args.checksum, args.specification)
    else:
        if args.checksum is not None:
            parser.error("--checksum requires --workbook")
        with TemporaryDirectory(prefix="rk-excel-example-") as directory:
            path = Path(directory) / "synthetic.xlsx"
            synthetic(path)
            review(path, sha256(path.read_bytes()).hexdigest(), args.specification)


if __name__ == "__main__":
    main()
