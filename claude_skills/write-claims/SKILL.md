---
name: write-claims
description: Invoke for claims.json final output format reference. Defines the schema for aggregated claims across all investigations.
---

# claims.json Format

Write to `/workspace/run/claims.json`. This is the final output file aggregating all claims from all investigations. Updated incrementally after each judge evaluation, finalized at the end of exploration.

## Schema

### Root fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | yes | From task_packet.json |
| `claims` | array | yes | All claims from all investigations (see below) |
| `top_supported_claim_id` | string | yes | The claim ID of the strongest overall finding. Set at finalization. |
| `investigation_summary` | array | yes | Summary of each investigation's outcome (see below) |

### Claim fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_id` | string | yes | Claim identifier (e.g. I1-claim1) |
| `investigation_id` | string | yes | Which investigation produced this claim |
| `investigation_name` | string | yes | Short label of the investigation |
| `role` | string | yes | One of: `main`, `alternative_explanation`, `artifact_check`, `robustness` |
| `text` | string | yes | Claim statement with key finding and numbers |
| `status` | string | yes | One of: `supported`, `weakened`, `refuted`, `inconclusive` |
| `confidence` | number | yes | Judge's calibrated confidence (0-1) |
| `dimensions` | object | yes | See dimensions below |
| `evidence_refs` | array of strings | yes | Experiment IDs that produced evidence for this claim |
| `supporting_stats` | object | no | Key statistics from the experiments |

### Dimensions fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `variables` | array of strings | yes | Column names involved |
| `relation` | string | yes | Type of relationship found |
| `context` | string | yes | Analysis context description |
| `direction` | string | yes | Direction or nature of the finding |

### Investigation summary fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `investigation_id` | string | yes | Investigation identifier |
| `name` | string | yes | Short label |
| `phenomenon` | string | yes | Full phenomenon description |
| `status` | string | yes | Final investigation status |
| `winning_claim_id` | string or null | yes | The claim that best explains the phenomenon |
| `claim_outcome_counts` | object | yes | Counts by claim status: `supported`, `weakened`, `refuted`, `inconclusive` |

## When to update

- **After each judge evaluation**: merge the investigation's claims into this file (upsert by claim_id). Use the judge's calibrated confidence, not your own.
- **At finalization**: set `top_supported_claim_id` and complete `investigation_summary` for all investigations.
