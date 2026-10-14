"""Capture actual structural validation inputs from the existing schema suites.

This instrumentation observes the original validator outcome without changing
tests, source schemas, or semantic validation. It is research tooling only.
"""

import hashlib
import json
from pathlib import Path
import runpy
import sys

from jsonschema import validators


suite = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
schemas, cases = {}, {}


def record(validator, document, accepted):
    schema = validator.schema
    if "rangekeeper" not in schema.get("$id", ""):
        return
    encoded_schema = json.dumps(schema, sort_keys=True)
    schema_id = hashlib.sha256(encoded_schema.encode()).hexdigest()[:16]
    encoded_document = json.dumps(document, sort_keys=True)
    case_id = hashlib.sha256((schema_id + encoded_document).encode()).hexdigest()[:16]
    schemas[schema_id] = schema
    row = dict(schema=schema_id, document=document, accepted=accepted)
    if case_id in cases:
        assert cases[case_id] == row
    cases[case_id] = row


def instrument(cls):
    original_validate, original_is_valid = cls.validate, cls.is_valid

    def validate(self, document, *args, **kwargs):
        try:
            result = original_validate(self, document, *args, **kwargs)
        except Exception:
            record(self, document, False)
            raise
        record(self, document, True)
        return result

    def is_valid(self, document, *args, **kwargs):
        result = original_is_valid(self, document, *args, **kwargs)
        record(self, document, result)
        return result

    cls.validate, cls.is_valid = validate, is_valid


for cls in set(validators._VALIDATORS.values()):
    instrument(cls)
sys.path.insert(0, str(suite.parent))
try:
    runpy.run_path(str(suite), run_name="__main__")
finally:
    (output / (suite.stem + ".json")).write_text(
        json.dumps(dict(suite=suite.name, schemas=schemas, cases=cases), indent=2) + "\n"
    )
