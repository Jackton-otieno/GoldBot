"""Append-only, hash-chained log of data examined in the personal research track.

Anything recorded here is exposed. It can support self-tested research but
can never be presented as unseen data for independent or prospective
validation. Each line carries the SHA-256 of the previous line, so deleting
or editing an earlier entry breaks the chain and is detected by ``verify``.
"""

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


DEFAULT_LOG = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "exposure-log.jsonl"
LABEL = "SELF_TESTED_EXPOSED"
GENESIS = "0" * 64


class ExposureLogError(ValueError):
    pass


def _lines(path):
    path = Path(path)
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ExposureLogError("Exposure log does not end with a newline; it may be truncated.")
    return raw.splitlines()


def verify(path=DEFAULT_LOG):
    """Return the entries after checking every link in the chain."""
    previous, entries = GENESIS, []
    for number, line in enumerate(_lines(path), start=1):
        try:
            entry = json.loads(line)
        except ValueError:
            raise ExposureLogError(f"Entry {number} is not valid JSON.") from None
        if entry.get("prev_entry_sha256") != previous or entry.get("label") != LABEL:
            raise ExposureLogError(f"Entry {number} breaks the hash chain.")
        previous = sha256(line).hexdigest()
        entries.append(entry)
    return entries


def append(*, source, sha256_digest, coverage_utc, purpose, tool, path=DEFAULT_LOG,
           clock=lambda: datetime.now(timezone.utc)):
    """Verify the existing chain, then append one exposure entry."""
    if not all(isinstance(v, str) and v.strip() for v in (source, purpose, tool)):
        raise ExposureLogError("source, purpose and tool are required.")
    if sha256_digest is not None and (len(sha256_digest) != 64
                                      or any(c not in "0123456789abcdef" for c in sha256_digest)):
        raise ExposureLogError("sha256_digest must be 64 lowercase hex characters or None.")
    if coverage_utc is not None and (len(coverage_utc) != 2 or coverage_utc[1] < coverage_utc[0]):
        raise ExposureLogError("coverage_utc must be [start, end] or None.")
    path = Path(path)
    lines = _lines(path)
    verify(path)
    entry = {
        "recorded_utc": clock().isoformat(),
        "label": LABEL,
        "source": source,
        "sha256": sha256_digest,
        "coverage_utc": None if coverage_utc is None else list(coverage_utc),
        "purpose": purpose,
        "tool": tool,
        "prev_entry_sha256": sha256(lines[-1]).hexdigest() if lines else GENESIS,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as output:
        output.write(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")
    return entry
