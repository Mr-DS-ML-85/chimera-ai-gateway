from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import List, Tuple

from core.config import SUPPLY_CHAIN_MANIFEST


def _is_pinned_requirement(line: str) -> bool:
    s = line.split("#", 1)[0].strip()

    if not s:
        return True

    if s.startswith(("-r ", "-c ", "--", "-e ")):
        return True

    if s.startswith(("git+", "file:", "http://", "https://")):
        return True

    if re.search(r"\s@\s", s):
        return True

    return ("==" in s) or ("===" in s)


def audit_requirements(
    path: str | Path | None = None,
) -> Tuple[str, List[str]]:
    manifest = Path(path or SUPPLY_CHAIN_MANIFEST)

    issues: List[str] = []

    if not manifest.exists():
        return "", [f"requirements manifest missing: {manifest}"]

    content = manifest.read_text(
        encoding="utf-8",
        errors="replace",
    )

    fingerprint = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()[:32]

    for raw in content.splitlines():
        s = raw.strip()

        if not s or s.startswith("#"):
            continue

        if not _is_pinned_requirement(s):
            issues.append(f"Unpinned dependency: {s}")

    return fingerprint, issues