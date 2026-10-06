"""Internal atomic local artifact writes shared by review orchestration."""

import json
import os
import tempfile
from pathlib import Path


def write_json(path, value):
    """Replace only a complete JSON file on the same filesystem."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, delete=False, encoding="utf-8"
        ) as file:
            temporary = Path(file.name)
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
