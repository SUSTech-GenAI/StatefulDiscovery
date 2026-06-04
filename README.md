# StatefulDiscovery

## Evidence-Calibrated Claim Formation in Open-Ended Scientific Discovery
![Agent overall diagram](imgs/figure2.png)

## 安装

```bash
git clone https://github.com/Nazzyyj/StatefulDiscovery.git
cd ./StatefulDiscovery
```

## 配置 Backbone 模型 API-KEY

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

## 数据准备+处理
StatefulDisocvery在3个benchmark共40个数据集上进行评估。因为我们的目的是open-ended的发现，需要将benchmark的所有测试问题剔除，让agent接收数据集本身进行开放式探索。我们在 [DiscoveryBench](https://huggingface.co/datasets/allenai/discoverybench), [BLADE](https://github.com/behavioral-data/BLADE)以及[BixBench](https://huggingface.co/datasets/phylobio/BixBench-Verified-50) 进行预处理，以屏蔽特定的查询和问题。

建议先下载处理DiscoveryBench进行测试。
```bash
# DiscoveryBench
hf download allenai/discoverybench --repo-type dataset --include 'discoverybench/real/test/**' --local-dir .
mv ./discoverybench/real/test/* ./discoverybench/
rmdir ./discoverybench/real/test ./discoverybench/real
rm -rf ./.cache
# 转换为open-ended任务，并写入 ./datasest/discoverybench/<task>/
python3 scripts/prepare_discoverybench_tasks.py
rm -rf ./discoverybench
```
``` bash
# BLADE
git clone --depth 1 --filter=blob:none --sparse https://github.com/behavioral-data/BLADE.git ./blade_repo
git -C ./blade_repo sparse-checkout set blade_bench/datasets
mkdir -p ./blade
cp -R ./blade_repo/blade_bench/datasets/* ./blade/
rm -rf ./blade_repo
# 转换为open-ended任务，并写入 ./datasest/blade/<task>/
python3 scripts/prepare_blade_tasks.py
rm -rf ./blade
```
``` bash
# BixBench-v50
mkdir -p ./bixbench/verified50 ./bixbench/full
hf download phylobio/BixBench-Verified-50 --repo-type dataset --local-dir ./bixbench/verified50
hf download futurehouse/BixBench BixBench.jsonl --repo-type dataset --local-dir ./bixbench/full
# 转换为open-ended任务，并写入 ./datasest/bixbench/<task>/
python3 scripts/prepare_bixbench_tasks.py
rm -rf ./bixbench
```

转换后的每个任务目录包含数据文件和 `task_packet.json`：

```text
datasets/xxx/<任务名>/
  数据文件...
  task_packet.json
```

`task_packet.json` 只包含 open-ended 运行需要的信息，包括 `task_id`、
`dataset_paths`、带列说明的 `column_metadata` 和 `budget`。其中 `task_id`
直接使用任务目录名。脚本不会把原始Benchmarks等含有的queries、hypotheses 或答案写入任务目录。

## 运行任务（Claude Code）
我们提供不同coding agent的支持，首先是Claude Code CLI，版本固定为 `2.1.76`。
相关文件放在独立路径下：

```text
dockerfiles/Dockerfile.claude
container/claude/CLAUDE.md
claude_skills/
scripts/run_claude_task.sh
```

运行单个任务：

```bash
./scripts/run_claude_task.sh datasets/discoverybench/nls_incarceration discovery_output/discoverybench/nls_incarceration
```

本项目也提供实时跟踪的看板，如果需要启动实时 dashboard，可以添加 `--dashboard 8050`。


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

## 运行任务（OpenCode）

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

其他可复用方法说明保留为 OpenCode skills。

## Experimental Rounds
以Bixbench中的bix-52为例，我们将其流程可视化为下图所示。

![case study](imgs/case_.png)