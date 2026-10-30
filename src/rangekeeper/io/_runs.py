"""Find stored Runs by the name of their Specification, in the order they finished.

``MemoryStore.find_runs`` and ``DirectoryStore.find_runs`` give their Runs to
``find_runs``; each store enumerates its own revisions.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from rangekeeper.run.run import Run
from rangekeeper.shared.arguments import require_text
from rangekeeper.shared.references import DocumentResolver

# The sort key of a Run that records no finish time: before every other Run.
_UNKNOWN = datetime.min.replace(tzinfo=UTC)


def find_runs(
    runs: Iterable[Run],
    *,
    specification: str,
    resolver: DocumentResolver,
) -> tuple[Run, ...]:
    """Return the Runs whose attempted Specification has the name ``specification``.

    The Runs come in the order of their recorded finish times, earliest first.
    A batch Run records no time of its own: it takes the latest finish time of
    its cases. A Run without a time comes first, and Runs with the same time
    keep their order in ``runs``. ``resolver`` supplies the Specification of
    each Run and the case Runs of each batch.
    """
    name = require_text(specification, "specification")
    names: dict[UUID, str | None] = {}
    found = [run for run in runs if _name(run, resolver, names) == name]
    return tuple(sorted(found, key=lambda run: _finished(run, resolver) or _UNKNOWN))


def _name(
    run: Run,
    resolver: DocumentResolver,
    names: dict[UUID, str | None],
) -> str | None:
    """Return the name of the Specification that ``run`` attempted, once for each."""
    identity = run.record.specification
    if identity not in names:
        names[identity] = resolver.load_specification(identity).metadata.name
    return names[identity]


def _finished(run: Run, resolver: DocumentResolver) -> datetime | None:
    """Return the recorded finish time of ``run``, or the latest of its cases."""
    runtime = run.report.runtime
    if runtime is not None and runtime.finished_at is not None:
        return datetime.fromisoformat(str(runtime.finished_at))
    times = [
        time
        for spawn in run.record.spawns or ()
        if (time := _finished(resolver.load_run(spawn), resolver)) is not None
    ]
    return max(times, default=None)
