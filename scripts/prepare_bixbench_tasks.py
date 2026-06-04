#!/usr/bin/env python3
"""Convert BixBench Verified-50 capsules into open-ended task bundles.

Input layout:
    bixbench/
        verified50/
            BixBench-Verified-50.jsonl
            CapsuleFolder-<uuid>.zip
            ...
        full/
            BixBench.jsonl

Output layout:
    datasets/bixbench/<bix-id>/
        data files...
        task_packet.json

The generated task packet excludes BixBench questions, answers, ideals, and
results. It deduplicates Verified-50 question rows by capsule UUID, merges
capsules that share the same bix-* short ID, and uses the full BixBench metadata
only to confirm each capsule's bix-* short ID.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_BUDGET = {
    "max_experiments": 40,
    "max_runtime_minutes": 90,
}

TABULAR_SUFFIXES = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
}

MISSING_VALUES = {"", "na", "n/a", "nan", "none", "null"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare BixBench Verified-50 open-ended tasks."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("bixbench"),
        help="Downloaded BixBench directory. Default: ./bixbench",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets") / "bixbench",
        help="Output task directory. Default: ./datasets/bixbench",
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_no}: {exc}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def capsule_uuid_from_folder(data_folder: str) -> str:
    name = Path(data_folder).name
    if name.startswith("CapsuleFolder-"):
        name = name[len("CapsuleFolder-") :]
    if name.endswith(".zip"):
        name = name[:-4]
    return name


def load_verified_capsules(source_dir: Path) -> list[dict[str, str]]:
    verified_path = source_dir / "verified50" / "BixBench-Verified-50.jsonl"
    if not verified_path.exists():
        raise FileNotFoundError(f"missing verified metadata: {verified_path}")

    capsules: dict[str, dict[str, str]] = {}
    for row in read_jsonl(verified_path):
        uuid = str(row.get("capsule_uuid") or "").strip()
        short_id = str(row.get("short_id") or "").strip()
        data_folder = str(row.get("data_folder") or "").strip()
        if not uuid and data_folder:
            uuid = capsule_uuid_from_folder(data_folder)
        if not uuid or not short_id:
            continue
        if not data_folder:
            data_folder = f"CapsuleFolder-{uuid}.zip"
        capsules.setdefault(
            uuid,
            {
                "capsule_uuid": uuid,
                "short_id": short_id,
                "data_folder": data_folder,
            },
        )
    return sorted(capsules.values(), key=lambda item: (item["short_id"], item["capsule_uuid"]))


def load_full_short_ids(source_dir: Path) -> dict[str, str]:
    full_path = source_dir / "full" / "BixBench.jsonl"
    if not full_path.exists():
        print(f"warning: full BixBench metadata not found: {full_path}", file=sys.stderr)
        return {}

    mapping: dict[str, str] = {}
    for row in read_jsonl(full_path):
        uuid = str(row.get("capsule_uuid") or "").strip()
        short_id = str(row.get("short_id") or "").strip()
        if uuid and short_id:
            mapping.setdefault(uuid, short_id)
    return mapping


def group_capsules(capsules: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_short: dict[str, list[dict[str, str]]] = {}
    for capsule in capsules:
        by_short.setdefault(capsule["short_id"], []).append(capsule)
    return {
        short_id: sorted(items, key=lambda item: item["capsule_uuid"])
        for short_id, items in sorted(by_short.items())
    }


def safe_member_path(member_name: str) -> PurePosixPath | None:
    path = PurePosixPath(member_name)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path


def copy_capsule_data(zip_path: Path, task_output: Path, rel_prefix: Path = Path(".")) -> list[Path]:
    copied = []
    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                safe_path = safe_member_path(info.filename)
                if safe_path is None:
                    raise ValueError(f"unsafe zip member path in {zip_path}: {info.filename}")
                if safe_path.parts and safe_path.parts[0].startswith("CapsuleData-"):
                    zf.extract(info, extract_dir)

        data_roots = sorted(path for path in extract_dir.iterdir() if path.name.startswith("CapsuleData-"))
        for data_root in data_roots:
            for src in sorted(path for path in data_root.rglob("*") if path.is_file()):
                rel = src.relative_to(data_root)
                dst = task_output / rel_prefix / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(dst)
    return copied


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


def infer_columns_from_csv(path: Path, source_file: str, max_rows: int = 100) -> list[dict]:
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
            "source_file": source_file,
        }
        for name, types in observed.items()
    ]


def infer_columns_from_excel(path: Path, source_file: str) -> list[dict]:
    try:
        import pandas as pd
    except ImportError:
        print(f"  warning: pandas not installed, skipping Excel metadata: {path}", file=sys.stderr)
        return []

    try:
        sheets = pd.read_excel(path, sheet_name=None, nrows=100)
    except Exception as exc:
        print(f"  warning: failed to infer columns from {path}: {exc}", file=sys.stderr)
        return []

    columns = []
    for sheet_name, frame in sheets.items():
        for name, dtype in frame.dtypes.items():
            columns.append(
                {
                    "name": str(name),
                    "type": str(dtype),
                    "source_file": source_file,
                }
            )
    return columns


def infer_columns(files: list[Path], task_output: Path) -> list[dict]:
    columns = []
    for path in files:
        if path.suffix.lower() not in TABULAR_SUFFIXES:
            continue
        source_file = path.relative_to(task_output).as_posix()
        try:
            if path.suffix.lower() in {".csv", ".tsv"}:
                columns.extend(infer_columns_from_csv(path, source_file))
            else:
                columns.extend(infer_columns_from_excel(path, source_file))
        except Exception as exc:
            print(f"  warning: failed to infer columns from {path}: {exc}", file=sys.stderr)
    return columns


def prepare_task(
    task_name: str,
    capsules: list[dict[str, str]],
    source_dir: Path,
    output_dir: Path,
    *,
    max_experiments: int,
    max_runtime_minutes: int,
) -> bool:
    task_output = output_dir / task_name
    task_output.mkdir(parents=True, exist_ok=True)

    files = []
    use_capsule_prefix = len(capsules) > 1
    for capsule in capsules:
        zip_path = source_dir / "verified50" / capsule["data_folder"]
        if not zip_path.exists():
            raise FileNotFoundError(f"missing capsule zip for {task_name}: {zip_path}")
        rel_prefix = Path(f"capsule_{capsule['capsule_uuid']}") if use_capsule_prefix else Path(".")
        files.extend(copy_capsule_data(zip_path, task_output, rel_prefix))

    rel_files = [path.relative_to(task_output).as_posix() for path in files]
    packet = {
        "task_id": task_name,
        "dataset_paths": rel_files,
        "column_metadata": infer_columns(files, task_output),
        "budget": {
            "max_experiments": max_experiments,
            "max_runtime_minutes": max_runtime_minutes,
        },
    }

    with (task_output / "task_packet.json").open("w", encoding="utf-8") as f:
        json.dump(packet, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(
        f"prepared {task_name}: "
        f"{len(capsules)} capsule(s), "
        f"{len(packet['dataset_paths'])} data files, "
        f"{len(packet['column_metadata'])} columns"
    )
    return True


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir
    output_dir = args.output_dir

    try:
        capsules = load_verified_capsules(source_dir)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not capsules:
        print(f"error: no capsules found under {source_dir}", file=sys.stderr)
        return 1

    full_short_ids = load_full_short_ids(source_dir)
    for capsule in capsules:
        full_short_id = full_short_ids.get(capsule["capsule_uuid"])
        if full_short_id and full_short_id != capsule["short_id"]:
            print(
                f"warning: short_id mismatch for {capsule['capsule_uuid']}: "
                f"verified={capsule['short_id']} full={full_short_id}",
                file=sys.stderr,
            )

    grouped = group_capsules(capsules)
    prepared = 0
    for task_name, task_capsules in grouped.items():
        try:
            ok = prepare_task(
                task_name,
                task_capsules,
                source_dir,
                output_dir,
                max_experiments=args.max_experiments,
                max_runtime_minutes=args.max_runtime_minutes,
            )
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if ok:
            prepared += 1

    print(f"Done: {prepared} task(s) prepared under {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
