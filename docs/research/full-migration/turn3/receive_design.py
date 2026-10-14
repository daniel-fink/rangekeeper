"""Read the pinned legacy design into a private local comparison artifact.

No publication or source mutation. Credentials are read from the existing local
configuration and never written to the report or payload.
"""

import hashlib
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from specklepy.api import client, operations
from specklepy.transports.server import ServerTransport

ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / "walkthrough/.env")
load_dotenv(ROOT / "src/.env")
token = os.getenv("SPECKLE_TOKEN")
if not token:
    raise SystemExit("Missing configured SPECKLE_TOKEN; live read remains unverified.")
speckle = client.SpeckleClient(host="app.speckle.systems")
speckle.authenticate_with_token(token)
root = operations.receive(
    obj_id="e7acaac21ae7e9369339900a4aaeb827",
    remote_transport=ServerTransport(stream_id="c0f66c35e3", client=speckle),
)
serialized = operations.serialize(root)
destination = Path("/private/tmp/rk-turn3-private/design.json")
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(serialized)
print(
    json.dumps(
        {
            "status": "received",
            "sha256": hashlib.sha256(serialized.encode()).hexdigest(),
            "bytes": len(serialized.encode()),
        }
    )
)
