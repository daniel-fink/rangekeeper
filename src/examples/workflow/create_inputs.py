"""Create small synthetic workbooks for the two checked-in workflow examples."""

import argparse
from pathlib import Path
from openpyxl import Workbook


def create(destination: Path, domain: str) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Schedule"
    prefix, suffix = ("A", "B") if domain == "accommodation" else ("P", "C")
    rows = [
        ("ID", "Group", "Size", "Label", "Other"),
        (prefix + "1", "L1", 0, "2" + suffix, "2" + suffix),
        (prefix + "2", "L1", None, "2" + suffix, "3" + suffix),
        (prefix + "3", "L2", 12, "unknown", None),
        (None, None, None, None, None),
        ("note", None, None, None, None),
        ("END", None, None, None, None),
    ]
    for row in rows:
        sheet.append(row)
    sheet["G1"] = "L1"
    sheet["G2"] = "L2"
    sheet["H1"] = 12
    path = destination / "schedule.xlsx"
    workbook.save(path)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--domain", choices=("accommodation", "equipment"), required=True
    )
    args = parser.parse_args()
    create(args.destination, args.domain)
