"""Deterministic component streams independent of process and dispatch order."""

import hashlib
import json


def stream_identifier(scenario_key: str, component: str) -> str:
    return hashlib.sha256(
        json.dumps(
            [scenario_key, component], separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def create_generator(master_seed: int, *, scenario_key: str, component: str):
    """Create a fresh PCG64 Generator from stable SeedSequence entropy.

    No global generator, worker number or Python hash participates. Each component
    gets its own stream, so adding another component cannot shift existing draws.
    """
    import numpy as np

    if (
        type(master_seed) is not int
        or master_seed < 0
        or not scenario_key
        or not component
    ):
        raise ValueError("seed must be nonnegative and stream names nonempty")
    digest = bytes.fromhex(stream_identifier(scenario_key, component))
    words = [int.from_bytes(digest[i : i + 4], "big") for i in range(0, len(digest), 4)]
    return np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([master_seed, *words]))
    )
