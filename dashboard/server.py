#!/usr/bin/env python3
"""
Real-time dashboard server for tracking autonomous scientific discovery agent progress.

Usage:
    python dashboard/server.py /path/to/task/dir [--port 8050]
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
import uvicorn


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Discovery agent dashboard server")
    parser.add_argument("task_dir", type=str, help="Path to the task directory")
    parser.add_argument("--port", type=int, default=8050, help="Port to serve on")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# File cache: stores (mtime, parsed_data) per filename
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[float, Any]] = {}


def _read_json_cached(filepath: Path) -> Optional[dict]:
    """Read and parse a JSON file, returning cached version on error or no change."""
    key = str(filepath)
    if not filepath.exists():
        _cache.pop(key, None)
        return None
    try:
        mtime = filepath.stat().st_mtime
        if key in _cache and _cache[key][0] == mtime:
            return _cache[key][1]
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache[key] = (mtime, data)
        return data
    except (json.JSONDecodeError, OSError):
        # Return cached version if available, else None
        if key in _cache:
            return _cache[key][1]
        return None


def _read_jsonl_cached(filepath: Path) -> Optional[list]:
    """Read a JSONL file (one JSON object per line or concatenated), with caching."""
    key = str(filepath)
    if not filepath.exists():
        _cache.pop(key, None)
        return None
    try:
        mtime = filepath.stat().st_mtime
        if key in _cache and _cache[key][0] == mtime:
            return _cache[key][1]
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return []
        records = []
        # Try line-by-line first (standard jsonl)
        lines = content.split("\n")
        if all(not l.strip() or l.strip().startswith("{") for l in lines):
            try:
                for line in lines:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
                _cache[key] = (mtime, records)
                return records
            except json.JSONDecodeError:
                records = []
        # Fallback: concatenated JSON objects (pretty-printed)
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(content):
            while idx < len(content) and content[idx] in " \t\n\r":
                idx += 1
            if idx >= len(content):
                break
            try:
                obj, end = decoder.raw_decode(content, idx)
                records.append(obj)
                idx = end
            except json.JSONDecodeError:
                break
        _cache[key] = (mtime, records)
        return records
    except OSError:
        if key in _cache:
            return _cache[key][1]
        return None


# ---------------------------------------------------------------------------
# File status helper
# ---------------------------------------------------------------------------

_WATCHED_FILES = [
    "task_packet.json",
    "epistemic_state.json",
    "patterns.json",
    "investigations.json",
    "claims.json",
    "experiments.jsonl",
    "claim_scores.json",
    "strategy_recommendation.json",
]


def _file_status(task_dir: Path) -> dict:
    result = {}
    for name in _WATCHED_FILES:
        fp = task_dir / name
        if fp.exists():
            st = fp.stat()
            result[name] = {"exists": True, "mtime": st.st_mtime, "size": st.st_size}
        else:
            result[name] = {"exists": False, "mtime": None, "size": None}
    return result


# ---------------------------------------------------------------------------
# Normalizer helpers — handle LLM schema drift
# ---------------------------------------------------------------------------

def _get(d: Optional[dict], *keys, default=None):
    """Try multiple keys on a dict, return first found or default."""
    if d is None:
        return default
    for k in keys:
        if k in d:
            return d[k]
    return default


def _normalize_epistemic(raw: Optional[dict]) -> Optional[dict]:
    """Normalize epistemic_state.json handling field name variants."""
    if raw is None:
        return None

    # exploration_progress — agent uses inconsistent field names
    ep = raw.get("exploration_progress", {})
    exps_used = _get(ep, "experiments_used", "experiments_run", default=0)
    budget_total = _get(ep, "budget_total", "max_experiments", default=None)
    budget_remaining = _get(ep, "budget_remaining", "experiments_remaining", default=None)
    # Derive budget_total from used + remaining if not directly available
    if budget_total is None and budget_remaining is not None and exps_used is not None:
        budget_total = exps_used + budget_remaining
    patterns_total = _get(ep, "patterns_total", "patterns_identified", default=None)
    patterns_explained = _get(ep, "patterns_explained", default=None)
    patterns_unexplained = _get(ep, "patterns_unexplained", default=None)
    # Derive unexplained from total - explained
    if patterns_unexplained is None and patterns_total is not None and patterns_explained is not None:
        patterns_unexplained = patterns_total - patterns_explained
    investigations_total = _get(ep, "investigations_total", "investigations_created", default=None)
    investigations_resolved = _get(ep, "investigations_resolved", default=None)
    investigations_active = _get(ep, "investigations_active", default=None)
    # Derive active from total - resolved - retired
    investigations_retired = _get(ep, "investigations_retired", default=0)
    if investigations_active is None and investigations_total is not None and investigations_resolved is not None:
        investigations_active = investigations_total - investigations_resolved - (investigations_retired or 0)
    # Derive cycle_id from decision_log length
    dl = raw.get("decision_log", [])
    cycle_id = _get(ep, "cycle_id", default=len(dl) if dl else None)
    # Derive phase from state
    phase = _get(ep, "phase", default=None)
    if phase is None:
        l1_raw = raw.get("level1", {})
        mode = _get(l1_raw, "recommended_mode", default=None)
        if mode == "stop":
            phase = "finalizing"
        elif investigations_total and investigations_total > 0:
            phase = "exploring"
        else:
            phase = "base"
    progress = {
        "phase": phase,
        "cycle_id": cycle_id,
        "experiments_used": exps_used,
        "budget_total": budget_total,
        "budget_remaining": budget_remaining,
        "patterns_total": patterns_total,
        "patterns_explained": patterns_explained,
        "patterns_unexplained": patterns_unexplained,
        "investigations_total": investigations_total,
        "investigations_active": investigations_active,
        "investigations_resolved": investigations_resolved,
        "investigations_retired": investigations_retired,
    }

    # level1
    l1_raw = raw.get("level1", {})
    level1 = {
        "frontier_status": _get(l1_raw, "frontier_status", default=None),
        "coverage": _get(l1_raw, "coverage_assessment", "coverage", default=None),  # may be absent in newer runs
        "frontier_rationale": _get(l1_raw, "frontier_rationale", default=None),
        "saturation": _get(l1_raw, "saturation_assessment", "saturation", default=None),
        "recommended_mode": _get(l1_raw, "recommended_mode", default=None),
        "rationale": _get(l1_raw, "rationale", "coverage_rationale", default=None),
        "saturation_rationale": _get(l1_raw, "saturation_rationale", default=None),
    }

    # level2
    l2_raw = raw.get("level2", {})
    level2 = {
        "active_investigation_id": _get(l2_raw, "active_investigation_id", default=None),
        "resolution_status": _get(l2_raw, "resolution_status", default=None),
        "resolution_confidence": _get(l2_raw, "resolution_confidence", default=None),
        "resolution_rationale": _get(l2_raw, "resolution_rationale", "rationale", default=None),
        "evidence_strength": _get(l2_raw, "evidence_strength", default=None),
        "red_flag_pressure": _get(l2_raw, "red_flag_pressure", default=None),
        "next_best_resolution_step": _get(l2_raw, "next_best_resolution_step", "next_best_step", default=None),
        "remaining_uncertainties": _get(l2_raw, "remaining_uncertainties", default=[]),
    }

    # meta_uncertainty
    meta_raw = raw.get("meta_uncertainty", {})
    meta = {
        "primary_type": _get(meta_raw, "primary_uncertainty_type", "primary_type", default=None),
        "rationale": _get(meta_raw, "primary_uncertainty_rationale", "description", "rationale", default=None),
        "best_information_gain_opportunity": _get(meta_raw, "best_information_gain_opportunity", default=None),
    }

    # active_focus
    af_raw = raw.get("active_focus", {})
    active_focus = {
        "investigation_id": _get(af_raw, "investigation_id", default=None),
        "frontier_summary": _get(af_raw, "frontier_summary", default=None),
        "current_risks": _get(af_raw, "current_risks", default=None),
    }

    # decision_log — entries may have different shapes
    raw_log = raw.get("decision_log", [])
    decision_log = []
    for idx, entry in enumerate(raw_log):
        target_raw = _get(entry, "target", default=None)
        if isinstance(target_raw, dict):
            target_str = _get(target_raw, "investigation_id", "pattern_id", default="")
        elif isinstance(target_raw, str):
            target_str = target_raw
        else:
            # Try to extract from action string
            action_str = _get(entry, "action", default="")
            import re
            m = re.search(r'(I\d+|P\d+)', action_str)
            target_str = m.group(1) if m else ""
        decision_log.append({
            "cycle_id": _get(entry, "cycle_id", "step", default=idx),
            "timestamp": _get(entry, "timestamp", default=None),
            "action": _get(entry, "action", default=""),
            "target": target_str,
            "rationale": _get(entry, "rationale", default=""),
            "outcome": _get(entry, "outcome", default=""),
        })

    return {
        "exploration_progress": progress,
        "level1": level1,
        "level2": level2,
        "meta_uncertainty": meta,
        "active_focus": active_focus,
        "decision_log": decision_log,
    }


def _normalize_patterns(raw: Optional[dict]) -> Optional[list]:
    """Normalize patterns.json handling field name variants."""
    if raw is None:
        return None
    patterns = raw.get("patterns", raw if isinstance(raw, list) else [])
    result = []
    for p in patterns:
        result.append({
            "id": _get(p, "id", "pattern_id", default="?"),
            "description": _get(p, "description", "observation", default=""),
            "priority": _get(p, "priority", default=0.5),
            "status": _get(p, "status", default="unknown"),
            "investigation_id": _get(p, "investigation_id", "explained_by_investigation", default=None),
            "base_experiment": _get(p, "base_experiment", "source", "source_experiment", default=None),
            "evidence": _get(p, "evidence", default=None),
            "explanation_summary": _get(p, "explanation_summary", default=None),
            "related_variables": _get(p, "related_variables", default=None),
        })
    return result


def _normalize_investigations(raw: Optional[dict]) -> Optional[dict]:
    """Normalize investigations.json handling field name variants."""
    if raw is None:
        return None
    investigations_list = raw.get("investigations", raw if isinstance(raw, list) else [])
    normalized = []
    for c in investigations_list:
        claims = []
        for cl in c.get("claims", []):
            claims.append({
                "claim_id": _get(cl, "claim_id", "id", default="?"),
                "role": _get(cl, "role", default=""),
                "text": _get(cl, "text", "statement", "description", default=""),
                "status": _get(cl, "status", default="unknown"),
                "supporting_evidence": _get(cl, "supporting_evidence", default=None),
                "counter_evidence": _get(cl, "counter_evidence", default=None),
            })
        queries = []
        for q in c.get("query_bundle", []):
            queries.append({
                "query_id": _get(q, "query_id", "id", default="?"),
                "claim_id": _get(q, "claim_id", default=None),
                "text": _get(q, "text", "description", default=""),
                "status": _get(q, "status", default="pending"),
                "result_ref": _get(q, "result_ref", default=None),
                "role": _get(q, "role", default=None),
                "depends_on": _get(q, "depends_on", default=None),
            })
        normalized.append({
            "id": _get(c, "investigation_id", "id", default="?"),
            "name": _get(c, "name", default=None),
            "phenomenon": _get(c, "phenomenon", default=""),
            "status": _get(c, "status", default="unknown"),
            "pattern_ids": _get(c, "pattern_ids", default=[]),
            "claims": claims,
            "query_bundle": queries,
        })
    return {"investigations": normalized}


def _normalize_claims(raw: Optional[dict]) -> Optional[dict]:
    """Normalize claims.json handling field name variants."""
    if raw is None:
        return None
    claims_list = raw.get("claims", [])
    normalized = []
    for cl in claims_list:
        normalized.append({
            "claim_id": _get(cl, "claim_id", "id", default="?"),
            "investigation_id": _get(cl, "investigation_id", default=None),
            "investigation_name": _get(cl, "investigation_name", default=None),
            "role": _get(cl, "role", default=""),
            "text": _get(cl, "text", "statement", "description", default=""),
            "status": _get(cl, "status", default="unknown"),
            "confidence": _get(cl, "confidence", default=None),
            "dimensions": _get(cl, "dimensions", default=None),
            "experiment_refs": _get(cl, "evidence_refs", "experiment_refs", default=[]),
        })
    return {
        "claims": normalized,
        "top_supported_claim_id": _get(raw, "top_supported_claim_id", default=None),
        "investigation_summary": _get(raw, "investigation_summary", default=None),
    }


def _normalize_experiments(records: Optional[list]) -> Optional[list]:
    """Normalize experiments.jsonl records."""
    if records is None:
        return None
    result = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        queries = []
        for q in rec.get("queries", []):
            if isinstance(q, str):
                queries.append({"query_id": q, "claim_id": None, "status": "unknown", "result_ref": None})
                continue
            queries.append({
                "query_id": _get(q, "query_id", "id", default="?"),
                "claim_id": _get(q, "claim_id", default=None),
                "status": _get(q, "status", default="unknown"),
                "result_ref": _get(q, "result_ref", default=None),
            })
        result.append({
            "experiment_id": _get(rec, "experiment_id", "id", default="?"),
            "investigation_id": _get(rec, "investigation_id", default=None),
            "phase": _get(rec, "phase", default=None),
            "status": _get(rec, "status", default="unknown"),
            "timestamp": _get(rec, "timestamp", default=None),
            "queries": queries,
            "code_file": _get(rec, "code_file", "code_path", default=None),
        })
    return result


def _normalize_scores(raw: Optional[dict]) -> Optional[dict]:
    """Normalize claim_scores.json handling field name variants."""
    if raw is None:
        return None
    adj = raw.get("adjudication_result", {})
    adjudication = {
        "status": _get(adj, "status", default=None),
        "summary": _get(adj, "summary", default=None),
        "winning_claim_id": _get(adj, "winning_claim_id", default=None),
        "confidence": _get(adj, "confidence", default=None),
        "remaining_uncertainties": _get(adj, "remaining_uncertainties", default=[]),
    }
    evals = []
    for ev in raw.get("claim_evaluations", []):
        evals.append({
            "claim_id": _get(ev, "claim_id", "id", default="?"),
            "role": _get(ev, "role", default=""),
            "status": _get(ev, "status", default="unknown"),
            "confidence": _get(ev, "confidence", default=None),
            "sanity_check": _get(ev, "sanity_check", default=None),
            "method_verification": _get(ev, "method_verification", default=None),
            "red_flags": _get(ev, "red_flags", default=[]),
            "concerns": _get(ev, "concerns", default=[]),
        })
    return {
        "investigation_id": _get(raw, "investigation_id", default=None),
        "cycle_id": _get(raw, "cycle_id", default=None),
        "adjudication_result": adjudication,
        "claim_evaluations": evals,
    }


def _normalize_strategy(raw: Optional[dict]) -> Optional[dict]:
    """Normalize strategy_recommendation.json."""
    if raw is None:
        return None
    budget = raw.get("budget_assessment", {})
    return {
        "action": _get(raw, "action", default=None),
        "target_pattern_id": _get(raw, "target_pattern_id", default=None),
        "target_investigation_id": _get(raw, "target_investigation_id", default=None),
        "rationale": _get(raw, "rationale", default=None),
        "decision_confidence": _get(raw, "decision_confidence", default=None),
        "budget_assessment": {
            "experiments_used": _get(budget, "experiments_used", default=None),
            "experiments_remaining": _get(budget, "experiments_remaining", default=None),
            "recommendation_basis": _get(budget, "recommendation_basis", default=None),
        },
    }


def _list_code_files(task_dir: Path) -> list[str]:
    """List filenames in the code/ subdirectory."""
    code_dir = task_dir / "code"
    if not code_dir.is_dir():
        return []
    try:
        return sorted(f.name for f in code_dir.iterdir() if f.is_file())
    except OSError:
        return []


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Discovery Agent Dashboard")

# Will be set from CLI args
TASK_DIR: Path = Path(".")


# ---------------------------------------------------------------------------
# Claim confidence accumulator — captures scores before they get overwritten
# ---------------------------------------------------------------------------
_confidence_store: dict[str, float] = {}  # claim_id -> confidence
_last_scores_investigation: Optional[str] = None


def _track_confidence(scores: Optional[dict]) -> dict[str, float]:
    """Accumulate per-claim confidence across investigation evaluations."""
    global _last_scores_investigation
    if scores is None:
        return _confidence_store

    investigation_id = scores.get("investigation_id")
    if investigation_id and investigation_id != _last_scores_investigation:
        # New investigation scores — save before overwrite
        _last_scores_investigation = investigation_id
        for ev in scores.get("claim_evaluations", []):
            cid = ev.get("claim_id", "")
            conf = ev.get("confidence")
            if cid and conf is not None:
                _confidence_store[cid] = conf

    return _confidence_store


# ---------------------------------------------------------------------------
# L1/L2 history tracker — accumulates snapshots across polls
# Persisted to {task_dir}/epistemic_trajectory.json so rationale survives restart
# ---------------------------------------------------------------------------
_l1l2_history: list[dict] = []
_l1l2_last_snapshot: Optional[str] = None  # JSON string for dedup
_l1l2_persist_path: Optional[str] = None   # set in init


def _l1l2_load(task_dir: str) -> None:
    """Load persisted trajectory on startup."""
    global _l1l2_history, _l1l2_last_snapshot, _l1l2_persist_path
    _l1l2_persist_path = os.path.join(task_dir, "epistemic_trajectory.json")
    if os.path.exists(_l1l2_persist_path):
        try:
            _l1l2_history = json.load(open(_l1l2_persist_path))
            if _l1l2_history:
                _l1l2_last_snapshot = json.dumps(_l1l2_history[-1], sort_keys=True)
        except Exception:
            _l1l2_history = []


def _l1l2_save() -> None:
    """Persist trajectory to disk."""
    if _l1l2_persist_path and _l1l2_history:
        try:
            with open(_l1l2_persist_path, "w") as f:
                json.dump(_l1l2_history, f, indent=2)
        except Exception:
            pass


def _track_l1l2(epistemic: Optional[dict]) -> list[dict]:
    """Append current L1/L2 snapshot if changed. Return full history."""
    global _l1l2_last_snapshot
    if epistemic is None:
        return _l1l2_history

    l1 = epistemic.get("level1", {})
    l2 = epistemic.get("level2", {})
    meta = epistemic.get("meta_uncertainty", {})
    prog = epistemic.get("exploration_progress", {})

    snapshot = {
        "cycle": prog.get("cycle_id"),
        "experiments_used": prog.get("experiments_used", 0),
        "frontier": l1.get("frontier_status"),
        "coverage": l1.get("coverage"),
        "saturation": l1.get("saturation"),
        "mode": l1.get("recommended_mode"),
        "l1_rationale": l1.get("rationale") or l1.get("saturation_rationale"),
        "active_investigation": l2.get("active_investigation_id"),
        "resolution": l2.get("resolution_status"),
        "confidence": l2.get("resolution_confidence"),
        "evidence": l2.get("evidence_strength"),
        "red_flags": l2.get("red_flag_pressure"),
        "l2_rationale": l2.get("resolution_rationale") or l2.get("rationale"),
        "meta_type": meta.get("primary_type"),
        "meta_rationale": meta.get("rationale") or meta.get("primary_uncertainty_rationale") or meta.get("description"),
        "meta_opportunity": meta.get("best_information_gain_opportunity"),
    }

    snap_json = json.dumps(snapshot, sort_keys=True)
    if snap_json != _l1l2_last_snapshot:
        _l1l2_last_snapshot = snap_json
        _l1l2_history.append(snapshot)
        _l1l2_save()

    # Fallback: reconstruct from decision_log if no persisted history
    if len(_l1l2_history) <= 1:
        dl = epistemic.get("decision_log", [])
        if len(dl) > 1:
            reconstructed = []
            n = len(dl)
            for i, entry in enumerate(dl):
                frac = i / max(n - 1, 1)
                if frac < 0.3:
                    f = "open"
                elif frac < 0.8:
                    f = "open"
                elif frac < 0.95:
                    f = "narrowing"
                else:
                    f = snapshot["frontier"] or "exhausted"
                reconstructed.append({
                    "cycle": entry.get("cycle_id", i),
                    "experiments_used": None,
                    "frontier": f,
                    "coverage": None,
                    "saturation": "low" if frac < 0.5 else ("medium" if frac < 0.85 else "high"),
                    "mode": "branch" if frac < 0.8 else (snapshot["mode"] or "stop"),
                    "l1_rationale": entry.get("rationale"),
                    "active_investigation": entry.get("target", ""),
                    "resolution": "open" if frac < 0.2 else ("partially_resolved" if frac < 0.5 else "resolved"),
                    "confidence": None,
                    "evidence": None,
                    "red_flags": None,
                    "l2_rationale": entry.get("rationale"),
                    "meta_type": None,
                    "meta_rationale": None,
                    "meta_opportunity": None,
                })
            reconstructed[-1] = snapshot
            return reconstructed

    return _l1l2_history


@app.get("/api/state")
def get_state():
    td = TASK_DIR

    # Read raw data
    task_raw = _read_json_cached(td / "task_packet.json")
    epistemic_raw = _read_json_cached(td / "epistemic_state.json")
    patterns_raw = _read_json_cached(td / "patterns.json")
    investigations_raw = _read_json_cached(td / "investigations.json")
    claims_raw = _read_json_cached(td / "claims.json")
    experiments_raw = _read_jsonl_cached(td / "experiments.jsonl")
    scores_raw = _read_json_cached(td / "claim_scores.json")
    strategy_raw = _read_json_cached(td / "strategy_recommendation.json")

    # Normalize task packet — extract key fields
    task = None
    if task_raw is not None:
        task = {
            "task_id": _get(task_raw, "task_id", default="unknown"),
            "dataset_paths": _get(task_raw, "dataset_paths", default=[]),
            "direction_hint": _get(task_raw, "direction_hint", default=None),
            "max_experiments": _get(
                task_raw.get("budget", {}), "max_experiments", default=None
            ),
            "max_runtime_minutes": _get(
                task_raw.get("budget", {}), "max_runtime_minutes", default=None
            ),
        }

    epistemic = _normalize_epistemic(epistemic_raw)
    l1l2_history = _track_l1l2(epistemic)
    confidence_store = _track_confidence(_normalize_scores(scores_raw))

    return JSONResponse({
        "task": task,
        "epistemic": epistemic,
        "patterns": _normalize_patterns(patterns_raw),
        "investigations": _normalize_investigations(investigations_raw),
        "claims": _normalize_claims(claims_raw),
        "experiments": _normalize_experiments(experiments_raw),
        "scores": _normalize_scores(scores_raw),
        "strategy": _normalize_strategy(strategy_raw),
        "code_files": _list_code_files(td),
        "file_status": _file_status(td),
        "l1l2_history": l1l2_history,
        "confidence_store": confidence_store,
    })


@app.get("/")
def serve_index():
    html_path = Path(__file__).parent / "index.html"
    return FileResponse(html_path, media_type="text/html")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    global TASK_DIR
    TASK_DIR = Path(args.task_dir).resolve()
    if not TASK_DIR.is_dir():
        print(f"Error: {TASK_DIR} is not a directory")
        raise SystemExit(1)
    print(f"Serving dashboard for: {TASK_DIR}")
    print(f"Open http://localhost:{args.port}")
    _l1l2_load(str(TASK_DIR))
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
