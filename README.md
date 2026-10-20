# StatefulDiscovery
[![arXiv: 2606.11851](https://img.shields.io/badge/arXiv-2606.11851-b31b1b.svg)](https://arxiv.org/abs/2606.11851) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

English | [中文](README_zh.md)

## Evidence-Calibrated Claim Formation in Open-Ended Scientific Discovery

StatefulDiscovery is a framework for open-ended scientific discovery agents. Unlike workflows that execute analyses for predefined questions, open-ended discovery requires an agent to decide, across multiple rounds of exploration, which emerging phenomena deserve further investigation while avoiding claims that exceed the evidential scope of the supporting analyses. To address this problem, StatefulDiscovery externalizes discovery state and uses it to coordinate frontier selection, evidence acquisition, and claim calibration, keeping exploration and claim formation aligned.

![Agent overall diagram](imgs/figure2.png)

## Installation

```bash
git clone https://github.com/SUSTech-GenAI/StatefulDiscovery.git
cd ./StatefulDiscovery
```

### Requirements

Host-side requirements:
- Docker
- Git
- Python 3.10+
- GitHub CLI (`gh`) for cloning the private development repository

Supported host platforms:
- macOS on Apple Silicon (`arm64`), using Docker Desktop
- Ubuntu Linux on AMD64 (`x86_64`) or ARM64 (`aarch64`), using Docker Engine

Other hosts capable of running Linux containers may also work, but are not currently verified.

Install Python utilities used for dataset download, task preparation, and the optional dashboard:

```bash
pip install -r requirements.txt
```

## Configure Backbone Model API Keys

Copy the configuration template:

```bash
cp config.env.example config.env
```

Then fill in the model configuration used by the agent inside the container:

```bash
ANTHROPIC_API_KEY=""
ANTHROPIC_BASE_URL="https://dashscope.aliyuncs.com/apps/anthropic"
ANTHROPIC_MODEL="qwen3.5-plus"
```

`config.env` is not committed to Git. The run scripts read this file and pass the configuration into the container.

## Data Preparation and Processing

StatefulDiscovery is evaluated on **40 datasets: 21 from BixBench, 13 from BLADE, and 6 from DiscoveryBench**. The exact task IDs and output paths are listed in [datasets/README.md](datasets/README.md), with a [datasets/paper_tasks.json](datasets/paper_tasks.json). Because our goal is open-ended discovery, benchmark-specific test questions must be removed so that the agent receives only the dataset itself and performs open-ended exploration. We preprocess [DiscoveryBench](https://huggingface.co/datasets/allenai/discoverybench), [BLADE](https://github.com/behavioral-data/BLADE), and [BixBench](https://huggingface.co/datasets/phylobio/BixBench-Verified-50) to hide task-specific queries and answers.

The commands below use `--task-list datasets/paper_tasks.json` to prepare the paper's selection. Omit this option to prepare all available tasks from a source benchmark. Use a fresh output directory for the exact 40-task set; the scripts do not remove previously prepared extra tasks.

We recommend starting with DiscoveryBench for a quick test. If access to
Hugging Face is slow or unavailable, you may need to configure a mirror first:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

```bash
# DiscoveryBench
hf download allenai/discoverybench --repo-type dataset --include 'discoverybench/real/test/**' --local-dir .
mv ./discoverybench/real/test/* ./discoverybench/
rmdir ./discoverybench/real/test ./discoverybench/real
rm -rf ./.cache
# Convert to open-ended tasks under ./datasets/discoverybench/<task>/
python3 scripts/prepare_discoverybench_tasks.py --task-list datasets/paper_tasks.json
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
python3 scripts/prepare_blade_tasks.py --task-list datasets/paper_tasks.json
rm -rf ./blade
```

```bash
# BixBench-v50
mkdir -p ./bixbench/verified50 ./bixbench/full
hf download phylobio/BixBench-Verified-50 --repo-type dataset --local-dir ./bixbench/verified50
hf download futurehouse/BixBench BixBench.jsonl --repo-type dataset --local-dir ./bixbench/full
# Convert to open-ended tasks under ./datasets/bixbench/<task>/
python3 scripts/prepare_bixbench_tasks.py --task-list datasets/paper_tasks.json
rm -rf ./bixbench
```

Each converted task directory contains data files and `task_packet.json`:

```text
datasets/xxx/<task_name>/
  data files...
  task_packet.json
```

`task_packet.json` contains only the information needed for open-ended runs, including `task_id`, `dataset_paths`, `column_metadata` with column descriptions, and `budget`. The `task_id` directly uses the task directory name. The scripts do not write original benchmark queries, hypotheses, or answers into task directories.

## Base Image Setup

StatefulDiscovery evaluates agents inside an isolated Docker environment for
fairness and reproducibility. Tasks run in Linux containers whether the host is
macOS or Ubuntu. The runtime images are built on
`futurehouse/bixbench:aviary-notebook-env`. The upstream image currently
supports only `linux/arm64`, so this repository also provides an AMD64-compatible
rebuild.

### ARM64 Hosts (macOS Apple Silicon / Ubuntu ARM64)

On an ARM64 host, pull the upstream image:

```bash
docker pull futurehouse/bixbench:aviary-notebook-env

# If a registry mirror is required:
# docker pull docker.1ms.run/futurehouse/bixbench:aviary-notebook-env
# docker tag docker.1ms.run/futurehouse/bixbench:aviary-notebook-env \
#   futurehouse/bixbench:aviary-notebook-env
```

### AMD64 Hosts (Ubuntu AMD64)

On an AMD64 host, build the compatible base image locally:

```bash
docker build \
  --platform linux/amd64 \
  --network host \
  -t futurehouse/bixbench:aviary-notebook-env \
  -f dockerfiles/Dockerfile.bixbench-base.amd64 \
  .
```

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
./scripts/run_claude_task.sh datasets/discoverybench/nls_incarceration discovery_output/discoverybench/nls_incarceration --dashboard 8050
```

The script automatically builds the Docker image `stateful-discovery-claude` and copies task data into a run directory:
The initial image build usually takes 5–10 minutes, and the Conda dependency-solving step may temporarily produce no new logs. Later runs normally reuse the Docker build cache.

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

## Citation

If you find this work useful, please cite:

```bibtex
@misc{chen2026statefuldiscoveryevidencecalibratedclaimformation,
      title={StatefulDiscovery: Evidence-Calibrated Claim Formation in Open-Ended Scientific Discovery},
      author={Jiayao Chen and Shi Liu and Linyi Yang},
      year={2026},
      eprint={2606.11851},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2606.11851},
}
```
