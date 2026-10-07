"""JSON encoding for review bundles; atomic publication belongs to IO."""

import json
from rangekeeper.io._atomic import replace


def write_json(path, value):
    return replace(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
