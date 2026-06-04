#!/usr/bin/env python3
"""Convert downloaded BLADE data into open-ended task bundles.

Input layout:
    blade/<task_name>/
        data.csv
        info.json
        annotations.csv
        mcq_dataset.json

Output layout:
    datasets/blade/<task_name>/
        data.csv
        task_packet.json

The generated task packet excludes BLADE research questions, annotations, and
MCQ answer files. It keeps only the data file, column metadata, and
open-ended exploration budget.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from typing import Any


DEFAULT_BUDGET = {
    "max_experiments": 40,
    "max_runtime_minutes": 90,
}

MISSING_VALUES = {"", "na", "n/a", "nan", "none", "null"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare BLADE open-ended tasks.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("blade"),
        help="Downloaded BLADE datasets directory. Default: ./blade",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets") / "blade",
        help="Output task directory. Default: ./datasets/blade",
    )
    parser.add_argument(
        "--max-experiments",
        type=int,
        default=DEFAULT_BUDGET["max_experiments"],
        help="Budget field for max experiments. Default: 40",
    )
    parser.add_argument(
        "--max-runtime-minutes",
        type=int,
        default=DEFAULT_BUDGET["max_runtime_minutes"],
        help="Budget field for max runtime minutes. Default: 90",
    )
    return parser.parse_args()


def load_info(task_dir: Path) -> dict[str, Any]:
    info_path = task_dir / "info.json"
    if not info_path.exists():
        print(f"  warning: missing info.json in {task_dir}", file=sys.stderr)
        return {}
    try:
        with info_path.open("r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"  warning: failed to read {info_path}: {exc}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def data_files(task_dir: Path, info: dict[str, Any]) -> list[Path]:
    names = {"data.csv"}
    data_path = info.get("data_path")
    if isinstance(data_path, str) and data_path.strip():
        names.add(Path(data_path).name)

    files = []
    for name in sorted(names):
        path = task_dir / name
        if path.is_file():
            files.append(path)
    return files


def infer_value_type(value: str) -> str | None:
    value = value.strip()
    if value.lower() in MISSING_VALUES:
        return None
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return "bool"
    try:
        int(value)
        return "int64"
    except ValueError:
        pass
    try:
        float(value)
        return "float64"
    except ValueError:
        return "object"


def merge_types(types: list[str]) -> str:
    if not types:
        return "object"
    if "object" in types:
        return "object"
    if "float64" in types:
        return "float64"
    if "int64" in types:
        return "int64"
    if "bool" in types:
        return "bool"
    return "object"


def normalize_header(header: list[str]) -> list[str]:
    normalized = []
    counts: dict[str, int] = {}
    for idx, raw_name in enumerate(header):
        name = raw_name.strip() if raw_name else f"Unnamed: {idx}"
        if name == "":
            name = f"Unnamed: {idx}"
        count = counts.get(name, 0)
        counts[name] = count + 1
        if count:
            name = f"{name}.{count}"
        normalized.append(name)
    return normalized


def infer_columns_from_csv(path: Path, max_rows: int = 100) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        try:
            header = normalize_header(next(reader))
        except StopIteration:
            return []

        observed: dict[str, list[str]] = {name: [] for name in header}
        for idx, row in enumerate(reader):
            if idx >= max_rows:
                break
            for col_idx, name in enumerate(header):
                value = row[col_idx] if col_idx < len(row) else ""
                value_type = infer_value_type(value)
                if value_type is not None:
                    observed[name].append(value_type)

    return [
        {
            "name": str(name),
            "type": merge_types(types),
            "source_file": path.name,
        }
        for name, types in observed.items()
    ]


def load_column_descriptions(info: dict[str, Any]) -> dict[str, str]:
    """Extract only column descriptions from BLADE info.json."""

    data_desc = info.get("data_desc", {})
    if not isinstance(data_desc, dict):
        return {}

    fields = data_desc.get("fields", [])
    if not isinstance(fields, list):
        return {}

    descriptions: dict[str, str] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("column", "")).strip()
        properties = field.get("properties", {})
        if not name or not isinstance(properties, dict):
            continue

        description = str(properties.get("description", "")).strip()
        if description:
            descriptions[name] = description
    return descriptions


def infer_columns(files: list[Path], info: dict[str, Any]) -> list[dict[str, Any]]:
    columns = []
    descriptions = load_column_descriptions(info)

    for path in files:
        try:
            inferred = infer_columns_from_csv(path)
        except Exception as exc:
            print(f"  warning: failed to infer columns from {path}: {exc}", file=sys.stderr)
            continue

        for column in inferred:
            description = descriptions.get(column["name"])
            if description:
                column["description"] = description
            columns.append(column)

    return columns


def prepare_task(
    task_dir: Path,
    output_dir: Path,
    *,
    max_experiments: int,
    max_runtime_minutes: int,
) -> bool:
    info = load_info(task_dir)
    files = data_files(task_dir, info)
    if not files:
        print(f"skip {task_dir.name}: no data files")
        return False

    task_output = output_dir / task_dir.name
    task_output.mkdir(parents=True, exist_ok=True)

    for src in files:
        shutil.copy2(src, task_output / src.name)

    packet = {
        "task_id": task_dir.name,
        "dataset_paths": [path.name for path in files],
        "column_metadata": infer_columns(files, info),
        "budget": {
            "max_experiments": max_experiments,
            "max_runtime_minutes": max_runtime_minutes,
        },
    }

    with (task_output / "task_packet.json").open("w", encoding="utf-8") as f:
        json.dump(packet, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(
        f"prepared {task_dir.name}: "
        f"{len(packet['dataset_paths'])} data files, "
        f"{len(packet['column_metadata'])} columns"
    )
    return True


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir
    output_dir = args.output_dir

    if not source_dir.exists():
        print(f"error: source directory not found: {source_dir}", file=sys.stderr)
        return 1
    if not source_dir.is_dir():
        print(f"error: source path is not a directory: {source_dir}", file=sys.stderr)
        return 1

    task_dirs = sorted(path for path in source_dir.iterdir() if path.is_dir())
    if not task_dirs:
        print(f"error: no task directories found in {source_dir}", file=sys.stderr)
        return 1

    prepared = 0
    for task_dir in task_dirs:
        if prepare_task(
            task_dir,
            output_dir,
            max_experiments=args.max_experiments,
            max_runtime_minutes=args.max_runtime_minutes,
        ):
            prepared += 1

    print(f"Done: {prepared} task(s) prepared under {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
