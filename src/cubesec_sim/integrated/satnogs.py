"""Auditable acquisition of public, passive SatNOGS observation fixtures."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

API = "https://network.satnogs.org/api/observations/{observation_id}/"
ALLOWED_HOSTS = {
    "network-satnogs.freetls.fastly.net",
    "s3.eu-central-1.wasabisys.com",
}


def _validated_data_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or not parsed.path.startswith(("/media/data_obs/", "/satnogs-network/data_obs/")):
        raise ValueError("SatNOGS fixture URL outside the allowlist")
    return url


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "CubeSec-Sim/1.0 academic fixture fetcher"})
    with urlopen(request, timeout=60) as response:  # nosec: URL is strictly allowlisted
        return response.read()


def fetch_observation(observation_id: int, output: Path) -> dict[str, object]:
    """Fetch audio and reference frames, never transmitting to SatNOGS."""
    if observation_id <= 0: raise ValueError("observation id must be positive")
    if output.exists(): raise FileExistsError(f"refusing to overwrite {output}")
    with urlopen(API.format(observation_id=observation_id), timeout=30) as response:  # nosec: fixed official API
        metadata = json.load(response)
    if metadata.get("id") != observation_id: raise ValueError("SatNOGS observation identity mismatch")
    if metadata.get("transmitter_mode") != "AFSK" or float(metadata.get("transmitter_baud") or 0) != 1200:
        raise ValueError("observation is not AFSK1200")
    audio_url = _validated_data_url(str(metadata.get("payload") or ""))
    audio_name = "audio" + (Path(urlparse(audio_url).path).suffix or ".ogg")
    downloads = [(audio_name, audio_url)]
    for index, item in enumerate(metadata.get("demoddata") or []):
        source = _validated_data_url(str(item["payload_demod"])); downloads.append((f"frames/frame-{index:04d}.bin", source))
    with ThreadPoolExecutor(max_workers=min(8, len(downloads))) as pool:
        blobs = list(pool.map(lambda item: _download(item[1]), downloads))
    output.mkdir(parents=True); (output/"frames").mkdir()
    files = []
    for (relative, source), data in zip(downloads, blobs):
        (output/relative).write_bytes(data)
        files.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "source": source})
    manifest = {
        "schema": 1, "provider": "SatNOGS Network", "observation_id": observation_id,
        "observation_api": API.format(observation_id=observation_id), "license": "CC-BY-SA-4.0",
        "attribution": f"SatNOGS observation {observation_id}; station {metadata.get('station_name')}; observer {metadata.get('observer')}",
        "metadata": metadata, "files": files,
    }
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return manifest
