"""Select named tasks from a benchmark entry in a JSON task manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def select_task_names(
    available: Iterable[str], task_list: Path | None, benchmark: str
) -> list[str]:
    """Preserve source order and reject incomplete or malformed selections."""
    names = list(available)
    if task_list is None:
        return names

    manifest = json.loads(task_list.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"task list must be a JSON object: {task_list}")
    selected = manifest.get(benchmark)
    if (
        not isinstance(selected, list)
        or not selected
        or any(not isinstance(name, str) or not name.strip() for name in selected)
    ):
        raise ValueError(f"task list must contain a nonempty string list for {benchmark}")
    if len(selected) != len(set(selected)):
        raise ValueError(f"duplicate task IDs in task list for {benchmark}")

    missing = sorted(set(selected) - set(names))
    if missing:
        raise ValueError(f"requested {benchmark} tasks missing from source: {', '.join(missing)}")
    selected_names = set(selected)
    return [name for name in names if name in selected_names]
