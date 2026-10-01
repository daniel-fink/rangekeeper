"""Check the research's reported outcomes, including known profile differences.

This freezes observations for the pinned experiment. A changed result may be an
upstream improvement; it does not imply that the dependency has become incorrect.
"""
from pathlib import Path
import json
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
read = lambda name: json.loads((root / name).read_text())
primary, cue, export = read("results.json"), read("cue-results.json"), read("export-results.json")
cases = read("cases.json")
valid = {"valid", "empty_constraints"}
semantic_errors = {"dangling_reference", "wrong_reference_kind", "numeric_constraint", "wrong_units", "duplicate_identity"}
structure_accepts = valid | semantic_errors
generated_extras = {"missing_expression_kind", "missing_declaration_kind", "abstract_expression"}
coercions = {"string_as_number", "bool_as_number"}
assert len(cases) == 20
for name in cases:
    structural = "accept" if name in structure_accepts else "reject"
    semantic = "accept" if name in valid else "reject"
    for checker in ("linkml_json_schema", "pydantic_strict", "pydantic_json_schema", "pydantic_semantic_export"):
        assert primary["results"][name][checker] == structural, (name, checker)
    assert primary["results"][name]["pydantic_with_semantics"] == semantic, name
    for mode, extras in (("strict", generated_extras), ("default", generated_extras | coercions)):
        expected = "accept" if name in structure_accepts | extras else "reject"
        assert primary["results"][name][f"linkml_pydantic_{mode}"] == expected, (name, mode)
    assert cue["results"][name]["#Model"] == structural, name
    assert cue["results"][name]["#SemanticModel"] == semantic, name
    for checker in ("typespec_json_schema", "cue_json_schema", "cue_semantic_export"):
        assert export["results"][name][checker] == structural, (name, checker)
assert cue["recursive_tree"]["accepted"]
assert export["typespec_recursive_tree"] == "accept"
assert export["cue_inverse"]["exit_code"] != 0
cardinality = read("cardinality-results.json")
assert cardinality["0"]["empty_constraints_accepted"]
assert not cardinality["1"]["empty_constraints_accepted"]
for value in cardinality.values():
    assert "1..*" in value["doc_rows"][0]
docs = read("documentation-results.json")
assert docs["top_level_mermaid_contains_none"]
assert docs["model_class_diagram_present"]
print("Confirmed the reported outcomes for all 20 fixtures, recursion, export, and documentation probes.")
