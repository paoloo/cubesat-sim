"""Stable independent random streams for paired experiments."""

from __future__ import annotations

import hashlib

import numpy as np


def _spawn_words(cell_id: str, replication: int) -> list[int]:
    digest = hashlib.sha256(f"{cell_id}\0{replication}".encode()).digest()
    return list(np.frombuffer(digest[:16], dtype="<u4"))


def rng_pair(
    master_seed: int, cell_id: str, replication: int
) -> tuple[np.random.Generator, np.random.Generator]:
    """Return separate channel/policy streams stable across processes and platforms."""
    if master_seed < 0 or replication < 0 or not cell_id:
        raise ValueError("invalid seed coordinates")
    root = np.random.SeedSequence(
        master_seed, spawn_key=tuple(_spawn_words(cell_id, replication))
    )
    channel_seed, policy_seed = root.spawn(2)
    return np.random.Generator(np.random.PCG64(channel_seed)), np.random.Generator(
        np.random.PCG64(policy_seed)
    )


def named_rng(
    master_seed: int, cell_id: str, replication: int, label: str
) -> np.random.Generator:
    """Order-independent stream for one named policy or analysis component."""
    if not label:
        raise ValueError("a non-empty stream label is required")
    words = _spawn_words(f"{cell_id}\0{label}", replication)
    seed = np.random.SeedSequence(master_seed, spawn_key=tuple(words))
    return np.random.Generator(np.random.PCG64(seed))
