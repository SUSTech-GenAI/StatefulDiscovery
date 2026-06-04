# StatefulDiscovery

## 安装

```bash
git clone https://github.com/Nazzyyj/StatefulDiscovery.git
cd ./StatefulDiscovery
```

## API 配置

复制配置模板：

```bash
cp config.env.example config.env
```

然后在 `config.env` 中填写运行容器内 agent 使用的模型配置：

```bash
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=
ANTHROPIC_MODEL=
```

`config.env` 不会提交到 Git；运行脚本会读取这个文件并将配置传入容器。

## 数据准备

### DiscoveryBench

#### 1. 下载原始数据

下载 DiscoveryBench 的 real test split，并将其中内容直接放到 `./discoverybench/` 下：

```bash
hf download allenai/discoverybench \
  --repo-type dataset \
  --include 'discoverybench/real/test/**' \
  --local-dir . && \
mv ./discoverybench/real/test/* ./discoverybench/ && \
rmdir ./discoverybench/real/test ./discoverybench/real && \
rm -rf ./.cache
```

#### 2. 转换为 open-ended 任务

将 `./discoverybench/<任务名>/` 转换为本项目运行使用的
`./datasets/discoverybench/<任务名>/` 结构：

```bash
python3 scripts/prepare_discoverybench_tasks.py
```

转换完成后，可以删除原始 DiscoveryBench 数据目录，只保留转换后的任务目录：

```bash
rm -rf ./discoverybench
```

转换后的每个任务目录包含数据文件和 `task_packet.json`：

```text
datasets/discoverybench/<任务名>/
  数据文件...
  task_packet.json
```

`task_packet.json` 只包含 open-ended 运行需要的信息，包括 `task_id`、
`dataset_paths`、带列说明的 `column_metadata` 和 `budget`。其中 `task_id`
直接使用任务目录名。脚本不会把 DiscoveryBench 原始 metadata 中的固定
queries、hypotheses 或答案写入任务目录。

### BLADE

#### 1. 下载原始数据

BLADE 数据在 GitHub 仓库的子目录中。使用 sparse checkout 只下载
`blade_bench/datasets`，并将其中内容直接放到 `./blade/` 下：

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/behavioral-data/BLADE.git ./blade_repo && \
git -C ./blade_repo sparse-checkout set blade_bench/datasets && \
mkdir -p ./blade && \
cp -R ./blade_repo/blade_bench/datasets/* ./blade/ && \
rm -rf ./blade_repo
```

#### 2. 转换为 open-ended 任务

将 `./blade/<任务名>/` 转换为本项目运行使用的
`./datasets/blade/<任务名>/` 结构：

```bash
python3 scripts/prepare_blade_tasks.py
```

转换完成后，可以删除原始 BLADE 数据目录，只保留转换后的任务目录：

```bash
rm -rf ./blade
```

转换后的每个任务目录包含 `data.csv` 和 `task_packet.json`：

```text
datasets/blade/<任务名>/
  data.csv
  task_packet.json
```

`task_packet.json` 只包含 open-ended 运行需要的信息，包括 `task_id`、
`dataset_paths`、带列说明的 `column_metadata` 和 `budget`。脚本不会把
BLADE 原始 `research_questions`、`annotations.csv` 或 `mcq_dataset.json` 写入任务目录。

### BixBench

#### 1. 下载原始数据

本项目使用 `phylobio/BixBench-Verified-50` 作为 BixBench 数据来源，并额外下载
`futurehouse/BixBench` 的 `BixBench.jsonl` 来校验 capsule UUID 和 `bix-*` 编号映射：

```bash
mkdir -p ./bixbench/verified50 ./bixbench/full && \
hf download phylobio/BixBench-Verified-50 \
  --repo-type dataset \
  --local-dir ./bixbench/verified50 && \
hf download futurehouse/BixBench BixBench.jsonl \
  --repo-type dataset \
  --local-dir ./bixbench/full
```

#### 2. 转换为 open-ended 任务

将 Verified-50 capsule 转换为本项目运行使用的
`./datasets/bixbench/<bix编号>/` 结构：

```bash
python3 scripts/prepare_bixbench_tasks.py
```

转换完成后，可以删除原始 BixBench 下载目录，只保留转换后的任务目录：

```bash
rm -rf ./bixbench
```

转换脚本会按 `capsule_uuid` 对 Verified-50 中的重复 question 去重，并按 `bix-*`
编号生成任务目录。如果同一个 `bix-*` 编号对应多个不同 capsule，会合并为同一个任务；
多 capsule 任务的数据会放在 `capsule_<uuid>/` 子目录下，避免文件名冲突。

转换后的每个任务目录包含 capsule data 文件和 `task_packet.json`：

```text
datasets/bixbench/<bix编号>/
  数据文件...
  task_packet.json
```

`task_packet.json` 只包含 open-ended 运行需要的信息，包括 `task_id`、
`dataset_paths`、`column_metadata` 和 `budget`。脚本不会把 BixBench 原始
`question`、`ideal`、`answer` 或 `result` 写入任务目录。对于 RNA、蛋白质序列等
没有表格列的 capsule，`column_metadata` 会是空数组。

## 运行任务（Claude Code）

Claude Code 后端相关文件放在独立路径下：

```text
dockerfiles/Dockerfile.claude
container/claude/CLAUDE.md
claude_skills/
scripts/run_claude_task.sh
```

运行单个任务：

```bash
./scripts/run_claude_task.sh datasets/discoverybench/nls_incarceration
```

也可以显式指定输出任务目录：

```bash
./scripts/run_claude_task.sh \
  datasets/discoverybench/nls_incarceration \
  discovery_output/discoverybench/nls_incarceration
```

如果需要启动实时 dashboard：

```bash
./scripts/run_claude_task.sh datasets/discoverybench/nls_incarceration --dashboard 8050
```

脚本会自动构建 Docker 镜像 `stateful-discovery-claude`，并将任务数据复制到运行目录：

```text
discovery_output/discoverybench/<任务名>/run_YYYYMMDD_HHMMSS/
```

容器运行时会将该运行目录挂载到 `/workspace/run`。任务数据和 agent 产出的
`patterns.json`、`experiments.jsonl`、`claims.json`、`report.md` 等结果都会写在
这个目录下。

Claude Code 的 `stream-json` 流式日志单独写入：

```text
discovery_log/discoverybench/<任务名>/run_YYYYMMDD_HHMMSS/stream.jsonl
```

该日志目录会挂载到容器内 `/workspace/log`，不会出现在 `/workspace/run` 的任务
数据目录中。`discovery_output/` 和 `discovery_log/` 都不会提交到 Git。

`dockerfiles/Dockerfile.claude` 中的 Claude Code CLI 版本固定为 `2.1.76`。

## 运行任务（OpenCode 实验版）

OpenCode 后端相关文件放在独立路径下：

```text
dockerfiles/Dockerfile.opencode
container/opencode/AGENTS.md
opencode_skills/
opencode_agents/
scripts/run_opencode_task.sh
```

运行方式与 Claude Code 版本一致：

```bash
./scripts/run_opencode_task.sh datasets/discoverybench/nls_incarceration
```

OpenCode 版本会自动构建 Docker 镜像 `stateful-discovery-opencode`。它复用
`config.env` 中的 `ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL` 和
`ANTHROPIC_MODEL`，并在运行时生成 OpenCode 配置。运行输出仍写入
`discovery_output/`，JSON 事件日志仍写入 `discovery_log/`。

`dockerfiles/Dockerfile.opencode` 中的 OpenCode CLI 版本固定为 `1.2.26`，
与当前 Claude Code `2.1.76` 的发布时间接近。

OpenCode 版本将 Claude Code 中 `context: fork` 的两个阶段改为 OpenCode
subagent：

```text
opencode_agents/investigation-decomposition.md
opencode_agents/experiment-runner.md
```

其他可复用方法说明保留为 OpenCode skills。该路径用于比较效果，默认主流程仍是
Claude Code 版本。
