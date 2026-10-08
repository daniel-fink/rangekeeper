"""Explicit read-only transport; caller supplies its authenticated SDK client."""

from dataclasses import dataclass
from importlib.metadata import version
from collections.abc import Mapping
from rangekeeper.shared import structured as _structured
from rangekeeper.adapters.speckle.errors import TransportError
from rangekeeper.adapters.speckle.objects import detach


@dataclass(frozen=True, slots=True)
class Received:
    """Detached received content and pinned source metadata; no domain claim yet."""

    payload: Mapping[str, object]
    source: Mapping[str, object]

    def __post_init__(self):
        object.__setattr__(self, "payload", _structured.freeze_mapping(self.payload))
        object.__setattr__(self, "source", _structured.freeze_mapping(self.source))


def receive(
    client,
    *,
    project_id: str,
    version_id: str | None = None,
    object_id: str | None = None,
) -> Received:
    """Receive one pinned object/version with no implicit latest selection.

    Authentication is the caller's responsibility. This reads the remote source;
    it does not publish, persist, convert, or execute the received content.
    SDK cache behavior belongs to the configured SDK transport.
    """
    if not project_id or bool(version_id) == bool(object_id):
        raise ValueError(
            "provide project_id and exactly one of version_id or object_id"
        )
    from specklepy.api import operations
    from specklepy.transports.server import ServerTransport

    try:
        resolved = (
            client.version.get(version_id, project_id).referenced_object
            if version_id
            else object_id
        )
        if not isinstance(resolved, str) or not resolved:
            raise TransportError(
                "Pinned version has no readable object reference; the service may "
                "restrict version history. Supply an independently recorded object "
                "pin only if it is the intended source. No latest version was selected."
            )
        payload = detach(
            operations.receive(
                obj_id=resolved,
                remote_transport=ServerTransport(stream_id=project_id, client=client),
            )
        )
    except TransportError:
        raise
    except Exception as error:
        raise TransportError(
            f"Receive failed for pinned project {project_id}"
        ) from error
    return Received(
        payload,
        {
            "project_id": project_id,
            "version_id": version_id,
            "object_id": resolved,
            "sdk": "specklepy",
            "sdk_version": version("specklepy"),
        },
    )
