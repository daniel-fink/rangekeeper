"""Public roots, codecs and writable/read-only interfaces retain static types."""

from pathlib import Path
from uuid import uuid4
import rangekeeper as rk
from rangekeeper.io import json, yaml, MemoryStore, DirectoryStore, RecordStore
from rangekeeper.references import DocumentResolver, SpecificationResolver
from rangekeeper.model import Metadata
from rangekeeper.run import RunRecord, Report, Status, Diagnostic, validate

model = rk.Model.create(metadata=Metadata(id=uuid4(), schema_version="0.5.0"))
loaded: rk.Model = json.loads(json.dumps(model), kind=rk.Model)
yaml_model: rk.Model = yaml.loads(yaml.dumps(model), kind=rk.Model)
store: RecordStore = MemoryStore()
resolver: DocumentResolver = DirectoryStore(Path("unused"))
investigation: SpecificationResolver = store
store.put(loaded)
spec = rk.Specification.from_data(
    {"metadata": {"id": str(uuid4()), "schema_version": "0.5.0"}}
)
store.put(spec)
run = rk.Run(
    RunRecord(
        metadata=Metadata(id=uuid4(), schema_version="0.1.0"),
        specification=spec.id,
        report=Report(
            status=Status(completion="failed", solution="not_assessed"),
            diagnostics=(
                Diagnostic(
                    severity="error",
                    code="specification_invalid",
                    message="No input supplied",
                ),
            ),
        ),
    )
)
validate(run, resolver=store)
restored: rk.Run = json.loads(json.dumps(run), kind=rk.Run)
