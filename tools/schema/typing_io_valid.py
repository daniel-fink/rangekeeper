"""Public roots, codecs and writable/read-only interfaces retain static types."""

from pathlib import Path
from uuid import uuid4

import rangekeeper as rk
from rangekeeper.io import DirectoryStore, MemoryStore, RecordStore, json, yaml
from rangekeeper.model import Metadata
from rangekeeper.run import (
    CompletionStatus,
    Diagnostic,
    Report,
    RunRecord,
    RunStatus,
    Severity,
    SolutionStatus,
    validate,
)
from rangekeeper.shared.references import DocumentResolver, SpecificationResolver

model = rk.Model.create(metadata=Metadata(id=uuid4(), schema_version="1.0.0"))
loaded: rk.Model = json.loads(text=json.dumps(model), kind=rk.Model)
yaml_model: rk.Model = yaml.loads(text=yaml.dumps(model), kind=rk.Model)
store: RecordStore = MemoryStore()
resolver: DocumentResolver = DirectoryStore(Path("unused"))
investigation: SpecificationResolver = store
store.put(loaded)
spec = rk.Specification.from_data(
    {"metadata": {"id": str(uuid4()), "schema_version": "1.0.0"}}
)
store.put(spec)
run = rk.Run(
    RunRecord(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        specification=spec.id,
        report=Report(
            status=RunStatus(
                completion=CompletionStatus.FAILED, solution=SolutionStatus.NOT_ASSESSED
            ),
            diagnostics=(
                Diagnostic(
                    severity=Severity.ERROR,
                    code="specification_invalid",
                    message="No input supplied",
                ),
            ),
        ),
    )
)
validate(run, resolver=store)
restored: rk.Run = json.loads(text=json.dumps(run), kind=rk.Run)
