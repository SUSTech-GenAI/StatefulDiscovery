#!/usr/bin/env python3
"""ReproGate checker — validates that claims have reproducible evidence.

Usage:
    python check_repro_gate.py <workspace_dir> <claims_json>

Checks:
    1. Each claim's evidence_refs exist in experiments.jsonl
    2. Each experiment has a code_path
    3. The code file exists and is non-empty
    4. The experiment has a status field

Output: JSON with passed/failed claim lists.
"""

import json
import sys
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def check_repro_gate(workspace_dir: Path, claims_path: Path) -> dict:
    experiments_path = workspace_dir / "experiments.jsonl"
    experiments = load_jsonl(experiments_path)
    exp_by_id = {e["experiment_id"]: e for e in experiments if "experiment_id" in e}

    claims_data = load_json(claims_path)
    claims = claims_data.get("claims", claims_data) if isinstance(claims_data, dict) else claims_data
    if isinstance(claims, dict):
        claims = [claims]

    passed = []
    failed = []

    for claim in claims:
        claim_id = claim.get("claim_id", "unknown")
        evidence_refs = claim.get("evidence_refs", [])

        if not evidence_refs:
            failed.append({"claim_id": claim_id, "reason": "no evidence_refs"})
            continue

        claim_ok = True
        for ref in evidence_refs:
            if ref not in exp_by_id:
                failed.append({
                    "claim_id": claim_id,
                    "reason": f"experiment {ref} not found in experiments.jsonl",
                })
                claim_ok = False
                break

            exp = exp_by_id[ref]

            if "status" not in exp:
                failed.append({
                    "claim_id": claim_id,
                    "reason": f"experiment {ref} has no status field",
                })
                claim_ok = False
                break

            code_path = exp.get("code_path", "")
            if not code_path:
                failed.append({
                    "claim_id": claim_id,
                    "reason": f"experiment {ref} has no code_path",
                })
                claim_ok = False
                break

            full_code_path = workspace_dir / code_path
            if not full_code_path.exists():
                failed.append({
                    "claim_id": claim_id,
                    "reason": f"code file {code_path} does not exist",
                })
                claim_ok = False
                break

            if full_code_path.stat().st_size == 0:
                failed.append({
                    "claim_id": claim_id,
                    "reason": f"code file {code_path} is empty",
                })
                claim_ok = False
                break

        if claim_ok:
            passed.append(claim_id)

    total = len(passed) + len(failed)
    return {
        "passed": passed,
        "failed": failed,
        "summary": f"{len(passed)}/{total} claims passed ReproGate",
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <workspace_dir> <claims_json>", file=sys.stderr)
        sys.exit(1)

    workspace = Path(sys.argv[1])
    claims_file = Path(sys.argv[2])

    if not workspace.is_dir():
        print(json.dumps({"error": f"workspace {workspace} is not a directory"}))
        sys.exit(1)
    if not claims_file.exists():
        print(json.dumps({"error": f"claims file {claims_file} does not exist"}))
        sys.exit(1)

    result = check_repro_gate(workspace, claims_file)
    print(json.dumps(result, indent=2))
