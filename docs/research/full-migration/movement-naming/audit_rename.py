"""Compare this rename with the verified wheel from the preceding checkpoint.

The old wheel must match the starting source hashes. Normalize only the approved
Flow names and compare Python syntax trees and generated record slot contracts.
"""

from pathlib import Path
import argparse
import ast
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--previous-site", type=Path, default=Path("/private/tmp/rk-flow-semantics-wheel/site"))
args = parser.parse_args()
before = json.loads((OUT / "before.json").read_text())


def rename(text):
    for old, new in (
        ("FlowSample", "Movement"),
        ("sample_coordinate", "movement_coordinate"),
        ("replace_samples", "replace_movements"),
        ("replace_sample", "replace_movement"),
    ):
        text = text.replace(old, new)
    text = re.sub(r"\bsamples\b", "movements", text)
    text = re.sub(r"\bsample\b", "movement", text)
    return re.sub(r"\bSamples\b", "Movements", text)


def previous(name):
    data = (args.previous_site / "rangekeeper" / name).read_bytes()
    expected = before["sha256"]["src/rangekeeper/" + name]
    assert hashlib.sha256(data).hexdigest() == expected, name
    return data.decode()


modules = (
    "model/flow.py", "model/_validation.py", "calculations/_flow.py",
    "calculations/series.py", "calculations/financial.py", "calculations/account.py",
    "adapters/pandas.py", "adapters/polars.py",
)
for name in modules:
    old = ast.dump(ast.parse(rename(previous(name))))
    new = ast.dump(ast.parse((ROOT / "src/rangekeeper" / name).read_text()))
    assert old == new, name
old_slots = json.loads(rename(previous("_schema/slots.json")))
new_slots = json.loads((ROOT / "src/rangekeeper/_schema/slots.json").read_text())
assert old_slots == new_slots
result = dict(
    previous_wheel_matches_starting_hashes=True,
    python_syntax_matches_after_naming_substitution=list(modules),
    generated_slot_contract_matches_after_naming_substitution=True,
)
(OUT / "rename-audit.json").write_text(json.dumps(result, indent=2) + "\n")
print("Eight runtime modules and generated slot contracts differ only by the approved naming substitution.")
