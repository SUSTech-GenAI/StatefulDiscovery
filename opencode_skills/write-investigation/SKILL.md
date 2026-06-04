---
name: write-investigation
description: Invoke for investigations.json and current_investigation.json format reference. Defines the schema for claim investigations and query bundles.
---

# Investigation Files Format

Two files share the same investigation structure:

- **`/workspace/run/investigations.json`** — cumulative record of all investigations. Root object with `investigations` array and `active_investigation_id` string.
- **`/workspace/run/current_investigation.json`** — the investigation currently being executed. Single investigation object (same structure as one element of the investigations array). Overwritten each cycle.

## Investigation fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Investigation identifier (I1, I2, ...) |
| `name` | string | yes | Short label for the investigation |
| `phenomenon` | string | yes | Full sentence describing the observed phenomenon being investigated |
| `adjudication_goal` | string | yes | What this investigation aims to determine — stated as a question or judgment to be made |
| `pattern_ids` | array of strings | yes | Pattern IDs this investigation addresses |
| `status` | string | yes | One of: `active`, `paused`, `resolved`, `retired`, `saturated` |
| `cycle_id` | integer | yes | Current cycle number for this investigation |
| `claims` | array | yes | Claims being evaluated (see below) |
| `query_bundle` | array | yes | Queries to execute (see below) |

### Investigation status values

- `active`: currently being investigated
- `paused`: temporarily set aside, may resume
- `resolved`: phenomenon explained, evidence sufficient
- `retired`: abandoned — artifact, low value, or merged with another investigation
- `saturated`: diminishing returns, not fully resolved but not worth continuing

## Claim fields (within `claims` array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Claim identifier (e.g. I1-claim1) |
| `text` | string | yes | The claim statement |
| `role` | string | yes | One of: `main`, `alternative_explanation`, `artifact_check`, `robustness` |
| `status` | string | yes | One of: `pending`, `supported`, `weakened`, `refuted`, `inconclusive` |
| `confidence` | number or null | yes | Judge's calibrated confidence (0-1), null if not yet evaluated |
| `supporting_evidence` | array | yes | Experiment IDs that support this claim |
| `counter_evidence` | array | yes | Experiment IDs that weaken or refute this claim |

### Claim roles

- `main`: the primary hypothesis about the phenomenon
- `alternative_explanation`: a competing explanation for the same phenomenon
- `artifact_check`: tests whether the phenomenon is an artifact of data processing, sampling, or annotation
- `robustness`: tests whether the main finding holds under different conditions or parameters

## Query fields (within `query_bundle` array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Query identifier (e.g. I1-q1) |
| `claim_id` | string | yes | Which claim this query tests |
| `text` | string | yes | The specific analysis to perform |
| `role` | string | yes | One of: `observational`, `diagnostic`, `artifact_check` |
| `expected_effect` | string | yes | What the result would mean for the claim — how it discriminates between explanations |
| `result_ref` | string or null | yes | Experiment ID that produced the result, null if not yet run |
| `depends_on` | array of strings | yes | Query IDs that must complete before this one (empty array if independent) |
| `status` | string | yes | One of: `pending`, `running`, `done`, `failed`, `skipped` |

## investigations.json additional field

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `active_investigation_id` | string or null | yes | ID of the currently active investigation |
