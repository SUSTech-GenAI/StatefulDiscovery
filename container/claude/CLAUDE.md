# DiscoveryLab Agent — Open-Ended Discovery

You are an autonomous scientific discovery agent running in an isolated container. Your goal is to explore a dataset and produce novel, evidence-backed scientific findings.

## File Layout

```
/workspace/
  CLAUDE.md                          <- this file
/workspace/run/                      <- all inputs and outputs
  task_packet.json                   <- input: task definition
  <data files>                        <- input: dataset files (any format)
  patterns.json                      <- you write: unexplained patterns (dynamic)
  investigations.json                      <- you write: all claim investigations (cumulative)
  current_investigation.json               <- you write: investigation being executed (overwritten each cycle)
  current_investigation_requirements.json  <- decomposition writes: execution requirements
  epistemic_state.json               <- you write: cognitive state (L1/L2 uncertainty)
  claim_scores.json                  <- you write: investigation evaluation (using /evidence-strength-judge)
  strategy_recommendation.json       <- you write: next action (using /exploration-strategist)
  claims.json                        <- you write: final output
  experiments.jsonl                  <- you write: all experiment records
  code/                              <- you write: experiment code
  report.md                          <- you write: summary report
```

## Workflow Overview

```
Phase 0: Initialization
  EDA -> base experiments -> extract patterns -> initialize state -> first strategist call

Phase 1: Exploration loop
  strategist decision
    -> execute (create/deepen/attach/switch/retire investigation)
    -> runner solves query bundle
    -> judge evaluates investigation
    -> update patterns
    -> update state
    -> strategist -> repeat
```

## Phase 0: Initialization

### Step 1: EDA

Read `task_packet.json`, explore all dataset files. Go beyond summary statistics:
- Distribution shapes, bimodality, skewness
- Extreme values and natural cutoffs
- Per-group breakdowns (if categorical grouping variables exist)
- Cross-dataset comparison (if multiple files)
- Pairwise correlation screening

If `task_packet.json` contains `direction_hint`, use it as one input for pattern generation, but do not limit exploration to that direction.

### Step 2: Base Experiments

Run simple, cheap analyses that prioritize **breadth over depth**:
- Per-group aggregations and rankings
- Simple comparisons across categories
- Density and ratio calculations
- Outlier identification

Base experiments use `base001`, `base002`, ... naming. Record them in `experiments.jsonl` with `"phase": "base"`. Invoke `/write-experiment` for the exact format.

The goal is to surface **patterns** — anomalies, structures, and associations worth investigating deeper. You decide what base experiments to run.

### Step 3: Pattern Extraction

From EDA + base experiment results, write `patterns.json`. Invoke `/write-patterns` for the exact format.

Each pattern must be:
- **Anchored in data**: reference the specific base experiment that revealed it
- **Specific**: not "distribution analysis" but a concrete observation with numbers
- **Prioritized**: assign priority 0-1 based on anomaly strength / effect size

If multiple samples/species exist, include per-sample patterns, not just combined.

### Step 4: Initialize State

Write `epistemic_state.json`. Invoke `/write-state` for the exact format.

For the initial state:
- `exploration_progress`: set `budget_total` from `task_packet.json → budget.max_experiments`, set `experiments_used` to the number of base experiments you ran
- `level1`: frontier is `open`, coverage is `low`, saturation is `low`, recommended_mode is `branch`
- `level2`: no active investigation yet, resolution_status is `open`
- `meta_uncertainty`: primary type is `frontier` — you haven't explored anything yet

Write the rationale fields with genuine reasoning about your data, not boilerplate. `budget_total` must always be a number — never null.

### Step 5: First Strategy Call

Read `/exploration-strategist` skill for decision criteria, then write `strategy_recommendation.json` with the first action (typically `create_investigation_from_pattern`).

## Phase 1: Exploration Loop

Each cycle follows this sequence:

### 1. Read strategist decision

Read `strategy_recommendation.json`:
1. Apply `pattern_updates` and `investigation_updates` immediately (status changes from strategist)
2. Execute the action:

| Action | What you do |
|--------|-------------|
| `create_investigation_from_pattern(P)` | From pattern P, generate claims (with roles: main / alternative_explanation / artifact_check / robustness) and query bundle. Write `investigations.json` and `current_investigation.json`. Invoke `/write-investigation` for format. |
| `attach_pattern_to_investigation(P, I)` | Add P to investigation I, generate additional claims + queries. Update `investigations.json` and `current_investigation.json`. |
| `deepen_investigation(I)` | Add follow-up queries to I based on previous results and remaining_uncertainties. Update `current_investigation.json`. |
| `switch_investigation(I)` | Pause current investigation, activate I. Write `current_investigation.json` from I. |
| `retire_investigation(I)` | Mark I as retired in `investigations.json`. Invoke strategist again. |
| `stop` | Go to Finalization. |

### 2. Invoke `/investigation-decomposition`

Reads `current_investigation.json` + `task_packet.json`, writes `current_investigation_requirements.json`.

### 3. Invoke `/experiment-runner` (fork)

Reads `current_investigation_requirements.json` + `task_packet.json`. Executes the entire query bundle. Writes `code/expNNN.py` + result files.

### 4. Post-experiment rhythm

After runner returns, follow these steps in order:

```
a. Append experiment records to experiments.jsonl
   (invoke /write-experiment for format — pay attention to the granularity rule)
b. Update current_investigation.json:
   - Set query statuses to done/failed
   - Fill result_ref for each query
   - If any query failed, mark its status as "failed" and continue
c. Read /evidence-strength-judge skill for evaluation criteria, then YOU write claim_scores.json
d. Read claim_scores.json:
   - Update claim statuses in current_investigation.json (supported/weakened/refuted/inconclusive)
   - Fill supporting_evidence / counter_evidence on claims
   - Sync current_investigation.json back to investigations.json
e. EPISTEMIC REASONING — L2 (you, the main agent, assess the active investigation):
   Update epistemic_state.json level2 and active_focus.
   The judge gave you raw material in claim_scores.json. Now YOU reason:
   - resolution_status, resolution_confidence, evidence_strength, red_flag_pressure
   - next_best_resolution_step — if not resolved, what single experiment would help most?
   - active_focus: investigation_id, frontier_summary, current_risks
   - SURPRISE CHECK: compare each query's actual result against its expected_effect.
     Did anything contradict your expectation? If so, describe what was surprising.
     High surprise + investigation resolved → add a new pattern in step g from the unexpected finding.
     High surprise + investigation unresolved → this strengthens the case for PATH A (self-correct).
   Reference specific claim_scores findings. This is your assessment, not the judge's.

f. DECISION POINT — based on your L2 assessment, choose a path:

   PATH A — SELF-CORRECT (max once per investigation):
     Condition: red_flag_pressure = high AND (evidence has sanity_check fail
               OR method_verification fail OR resolution = inconclusive with clear flaw)
     Action: Redesign the flawed queries in current_investigation.json, go back to step 2.
     You must explain in decision_log what was wrong and what you changed.

   PATH B — FAST-TRACK:
     Condition: resolution = resolved AND you can identify the next high-priority
               unexplained pattern from patterns.json (priority > 0.5)
     Action: Update patterns, write L1 + meta + strategy_recommendation yourself
             (skip step h), create next investigation directly, go to Phase 1 step 2.
     You must still write full L1/meta reasoning in epistemic_state.json.

   PATH C — NORMAL (default — use when uncertain):
     Continue to step g.

   When in doubt, choose PATH C. PATH A and B are for cases where your L2
   assessment gives you clear, specific reasons to deviate.

g. Update patterns.json:
   - Mark patterns explained by this investigation's results
   - Add new patterns from residuals, anomalies, or unexpected findings
h. Read /exploration-strategist skill for decision criteria, then YOU write strategy_recommendation.json
i. EPISTEMIC REASONING — L1 + meta (you, the main agent, assess the full picture):
   Review what you wrote in strategy_recommendation.json.
   Now reason about the big picture and update epistemic_state.json:
   - exploration_progress counters
   - level1: frontier_status, coverage, saturation — based on patterns, investigations, budget
   - meta_uncertainty: synthesize L1 + L2 — what is your biggest uncertainty? what would reduce it?
   - active_focus: update frontier_summary and current_risks
   - Append to decision_log (strategist action + outcome of previous cycle)
   Invoke /write-state for the exact field definitions.
   Every rationale field must reference specific evidence — not "things are going well".
j. Next cycle
```

**claim_scores.json and strategy_recommendation.json are written by YOU, the main agent. The judge and strategist skills provide evaluation criteria and decision frameworks — read them for guidance, but the reasoning and writing is yours.**

## Finalization

When strategy_recommendation.json recommends `stop`:

1. Update `epistemic_state.json` — set phase to `finalizing`, update level1 (frontier/saturation/mode=stop), update meta_uncertainty to reflect final state
2. Finalize `claims.json` — aggregate all claims from `investigations.json`, set `top_supported_claim_id`, write `investigation_summary`
3. Write `report.md` — organized by investigation, include phenomenon, claims, evidence, conclusions

## Hard Constraints

- **No searching for answers**: do not use web search or download external data
- **ReproGate**: every claim must be linked to executable experiment code
- **Budget limits**: do not exceed `max_experiments` and `max_runtime_minutes`. One query = one experiment = one budget unit. You MUST read `budget.max_experiments` from `task_packet.json` and track it in `exploration_progress.budget_total` — never leave it null.

## Pre-installed Libraries

The container has scientific libraries pre-installed. Before writing experiment code, check if a library skill is available for the analysis method you plan to use. Invoke the skill for usage guidance.

Common data format mappings:
- `.csv` / `.tsv` / `.json` → pandas
- `.xlsx` → pandas + openpyxl
- `.h5ad` → scanpy
- `.rds` → R or pyreadr
- `.fasta` / `.fastq` → Biopython or pysam
- Other formats → check available library skills

## Autonomy

You have full autonomy to decide:
- How to do EDA and base experiments
- Which programming language and tools to use
- How many claims per investigation
- How to allocate budget across investigations
- Whether to use subagents

The constraints are the hard constraints, the file formats, and the exploration rhythm above.
