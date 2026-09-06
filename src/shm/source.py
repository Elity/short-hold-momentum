from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


_FULL_GIT_SHA = re.compile(r"[0-9a-fA-F]{40}")


def source_revision(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        result = None

    if result is not None and result.returncode == 0:
        return result.stdout.strip()

    revision = os.environ.get("SHM_SOURCE_REVISION", "")
    if not _FULL_GIT_SHA.fullmatch(revision):
        raise RuntimeError(
            "source revision unavailable: SHM_SOURCE_REVISION must be a 40-character hexadecimal SHA"
        )
    return revision
