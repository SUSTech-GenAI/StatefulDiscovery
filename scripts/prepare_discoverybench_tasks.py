#!/usr/bin/env python3
"""Convert downloaded DiscoveryBench data into open-ended task bundles.

Input layout:
    discoverybench/<task_name>/
        data files...
        metadata_*.json

Output layout:
    datasets/discoverybench/<task_name>/
        data files...
        task_packet.json

The generated task packet intentionally excludes DiscoveryBench queries,
hypotheses, and answers. It only contains the data files, column metadata, and
the default open-ended exploration budget.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path


DEFAULT_BUDGET = {
    "max_experiments": 40,
    "max_runtime_minutes": 90,
}

DATA_SUFFIXES = {
    ".csv",
    ".tsv",
    ".txt",
    ".jsonl",
    ".xlsx",
    ".xls",
}

TABULAR_SUFFIXES = {
    ".csv",
    ".tsv",
}

MISSING_VALUES = {"", "na", "n/a", "nan", "none", "null"}
ColumnDescriptions = dict[tuple[str, str], str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare query-free DiscoveryBench open-ended tasks."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("discoverybench"),
        help="Downloaded DiscoveryBench real/test directory. Default: ./discoverybench",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets") / "discoverybench",
        help="Output task directory. Default: ./datasets/discoverybench",
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


def is_metadata_file(path: Path) -> bool:
    # Metadata is used for column descriptions, but not copied into task bundles.
    return path.name.startswith("metadata_") and path.suffix == ".json"


def data_files(task_dir: Path) -> list[Path]:
    files = []
    for path in sorted(task_dir.iterdir()):
        if not path.is_file() or is_metadata_file(path):
            continue
        if path.suffix.lower() in DATA_SUFFIXES:
            files.append(path)
    return files


def load_column_descriptions(task_dir: Path) -> ColumnDescriptions:
    """Read only dataset and column descriptions from DiscoveryBench metadata."""

    descriptions: ColumnDescriptions = {}
    for metadata_path in sorted(task_dir.glob("metadata_*.json")):
        try:
            with metadata_path.open("r", encoding="utf-8", errors="replace") as f:
                metadata = json.load(f)
        except Exception as exc:
            print(f"  warning: failed to read {metadata_path}: {exc}", file=sys.stderr)
            continue

        for dataset in metadata.get("datasets", []):
            dataset_name = Path(str(dataset.get("name", ""))).name
            columns = dataset.get("columns", {})
            if not dataset_name or not isinstance(columns, dict):
                continue

            for column_group in columns.values():
                if not isinstance(column_group, list):
                    continue
                for column in column_group:
                    if not isinstance(column, dict):
                        continue
                    name = str(column.get("name", "")).strip()
                    description = str(column.get("description", "")).strip()
                    if not name or not description:
                        continue
                    descriptions.setdefault((dataset_name, name), description)

                    # Metadata calls empty CSV index headers "Unnamed"; the
                    # CSV reader path normalizes those headers to "Unnamed: 0".
                    if name == "Unnamed":
                        descriptions.setdefault((dataset_name, "Unnamed: 0"), description)
    return descriptions


def sniff_dialect(path: Path, sample: str) -> csv.Dialect:
    if path.suffix.lower() == ".tsv":
        return csv.excel_tab
    try:
        return csv.Sniffer().sniff(sample)
    except csv.Error:
        return csv.excel


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


def infer_columns_from_csv(path: Path, max_rows: int = 100) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        reader = csv.reader(f, dialect=sniff_dialect(path, sample))
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


def infer_columns(files: list[Path], descriptions: ColumnDescriptions) -> list[dict]:
    columns = []
    for path in files:
        if path.suffix.lower() not in TABULAR_SUFFIXES:
            continue
        try:
            inferred = infer_columns_from_csv(path)
        except Exception as exc:
            print(f"  warning: failed to infer columns from {path}: {exc}", file=sys.stderr)
            continue
        for column in inferred:
            name = column["name"]
            description = descriptions.get((path.name, name))
            if description:
                column["description"] = description
            columns.append(column)
    return columns


def copy_data_file(src: Path, dst: Path) -> None:
    shutil.copy2(src, dst)


def prepare_task(
    task_dir: Path,
    output_dir: Path,
    *,
    max_experiments: int,
    max_runtime_minutes: int,
) -> bool:
    files = data_files(task_dir)
    if not files:
        print(f"skip {task_dir.name}: no data files")
        return False

    task_output = output_dir / task_dir.name
    task_output.mkdir(parents=True, exist_ok=True)

    for src in files:
        copy_data_file(src, task_output / src.name)

    descriptions = load_column_descriptions(task_dir)
    packet = {
        "task_id": task_dir.name,
        "dataset_paths": [path.name for path in files],
        "column_metadata": infer_columns(files, descriptions),
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
