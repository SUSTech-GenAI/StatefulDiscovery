# StatefulDiscovery
[![ArXiv: coming soon](https://img.shields.io/badge/ArXiv-coming_soon-b31b1b.svg)](imgs/paper.pdf) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

English | [中文](README_zh.md)

## Evidence-Calibrated Claim Formation in Open-Ended Scientific Discovery

StatefulDiscovery is a framework for open-ended scientific discovery agents. Unlike workflows that execute analyses for predefined questions, open-ended discovery requires an agent to decide, across multiple rounds of exploration, which emerging phenomena deserve further investigation while avoiding claims that exceed the evidential scope of the supporting analyses. To address this problem, StatefulDiscovery externalizes discovery state and uses it to coordinate frontier selection, evidence acquisition, and claim calibration, keeping exploration and claim formation aligned.

![Agent overall diagram](imgs/figure2.png)

## Installation

```bash
git clone https://github.com/Nazzyyj/StatefulDiscovery-Dev.git
cd ./StatefulDiscovery-Dev
```

## Configure Backbone Model API Keys

Copy the configuration template:

```bash
cp config.env.example config.env
```

Then fill in the model configuration used by the agent inside the container:

```bash
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=
ANTHROPIC_MODEL=
```

`config.env` is not committed to Git. The run scripts read this file and pass the configuration into the container.

## Data Preparation and Processing

StatefulDiscovery is evaluated on 40 datasets across 3 benchmarks. Because our goal is open-ended discovery, benchmark-specific test questions must be removed so that the agent receives only the dataset itself and performs open-ended exploration. We preprocess [DiscoveryBench](https://huggingface.co/datasets/allenai/discoverybench), [BLADE](https://github.com/behavioral-data/BLADE), and [BixBench](https://huggingface.co/datasets/phylobio/BixBench-Verified-50) to hide task-specific queries and answers.

We recommend starting with DiscoveryBench for a quick test.

```bash
# DiscoveryBench
hf download allenai/discoverybench --repo-type dataset --include 'discoverybench/real/test/**' --local-dir .
mv ./discoverybench/real/test/* ./discoverybench/
rmdir ./discoverybench/real/test ./discoverybench/real
rm -rf ./.cache
# Convert to open-ended tasks under ./datasets/discoverybench/<task>/
python3 scripts/prepare_discoverybench_tasks.py
rm -rf ./discoverybench
```

```bash
# BLADE
git clone --depth 1 --filter=blob:none --sparse https://github.com/behavioral-data/BLADE.git ./blade_repo
git -C ./blade_repo sparse-checkout set blade_bench/datasets
mkdir -p ./blade
cp -R ./blade_repo/blade_bench/datasets/* ./blade/
rm -rf ./blade_repo
# Convert to open-ended tasks under ./datasets/blade/<task>/
python3 scripts/prepare_blade_tasks.py
rm -rf ./blade
```

```bash
# BixBench-v50
mkdir -p ./bixbench/verified50 ./bixbench/full
hf download phylobio/BixBench-Verified-50 --repo-type dataset --local-dir ./bixbench/verified50
hf download futurehouse/BixBench BixBench.jsonl --repo-type dataset --local-dir ./bixbench/full
# Convert to open-ended tasks under ./datasets/bixbench/<task>/
python3 scripts/prepare_bixbench_tasks.py
rm -rf ./bixbench
```

Each converted task directory contains data files and `task_packet.json`:

```text
datasets/xxx/<task_name>/
  data files...
  task_packet.json
```

`task_packet.json` contains only the information needed for open-ended runs, including `task_id`, `dataset_paths`, `column_metadata` with column descriptions, and `budget`. The `task_id` directly uses the task directory name. The scripts do not write original benchmark queries, hypotheses, or answers into task directories.

## Running Tasks with Claude Code

We support multiple coding-agent backends. The primary backend is Claude Code CLI, pinned to version `2.1.76`.

The related files are isolated under:

```text
dockerfiles/Dockerfile.claude
container/claude/CLAUDE.md
claude_skills/
scripts/run_claude_task.sh
```

Run a single task:

```bash
./scripts/run_claude_task.sh datasets/discoverybench/nls_incarceration discovery_output/discoverybench/nls_incarceration
```

This project also provides a live dashboard for tracking agent progress:

```bash
pip install fastapi uvicorn

./scripts/run_claude_task.sh datasets/discoverybench/nls_incarceration discovery_output/discoverybench/nls_incarceration --dashboard 8050
```

The script automatically builds the Docker image `stateful-discovery-claude` and copies task data into a run directory:

```text
discovery_output/discoverybench/<task_name>/run_YYYYMMDD_HHMMSS/
```

At runtime, the container mounts this run directory at `/workspace/run`. Task data and agent outputs such as `patterns.json`, `experiments.jsonl`, `claims.json`, and `report.md` are written into this directory.

Claude Code `stream-json` logs are written separately:

```text
discovery_log/discoverybench/<task_name>/run_YYYYMMDD_HHMMSS/stream.jsonl
```

## Running Tasks with OpenCode

OpenCode backend files are isolated under:

```text
dockerfiles/Dockerfile.opencode
container/opencode/AGENTS.md
opencode_skills/
opencode_agents/
scripts/run_opencode_task.sh
```

The run interface is the same as the Claude Code version:

```bash
./scripts/run_opencode_task.sh datasets/discoverybench/nls_incarceration
```

The OpenCode version automatically builds the Docker image `stateful-discovery-opencode`. It reuses `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, and `ANTHROPIC_MODEL` from `config.env`, and generates the OpenCode configuration at runtime. Run outputs are written to `discovery_output/`, and JSON event logs are written to `discovery_log/`.

`dockerfiles/Dockerfile.opencode` pins the OpenCode CLI version to `1.2.26`, which is close in release time to the current Claude Code `2.1.76` version.

The OpenCode version maps the two Claude Code `context: fork` stages to OpenCode subagents:

```text
opencode_agents/investigation-decomposition.md
opencode_agents/experiment-runner.md
```

Other reusable method instructions are kept as OpenCode skills.

## Experimental Rounds

The following figure visualizes an example run on `bix-52` from BixBench.

![case study](imgs/case_.png)

## License

This repository is released under the MIT License. Datasets used by the benchmark preparation scripts are subject to their original licenses.
