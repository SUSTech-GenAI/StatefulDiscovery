# Datasets

StatefulDiscovery's main open-ended evaluation uses **40 datasets: 21 from BixBench, 13 from BLADE, and 6 from DiscoveryBench**. The table below lists the exact selection. [paper_tasks.json](paper_tasks.json) provides the same IDs in a machine-readable format.

## Evaluated datasets

| Benchmark | Datasets | Evaluated task IDs |
| --- | ---: | --- |
| [BixBench-Verified-50](https://huggingface.co/datasets/phylobio/BixBench-Verified-50) | 21 | `bix-6`, `bix-14`, `bix-16`, `bix-18`, `bix-22`, `bix-24`, `bix-26`, `bix-27`, `bix-30`, `bix-31`, `bix-32`, `bix-37`, `bix-41`, `bix-43`, `bix-46`, `bix-49`, `bix-51`, `bix-52`, `bix-53`, `bix-55`, `bix-61` |
| [BLADE](https://github.com/behavioral-data/BLADE/tree/main/blade_bench/datasets) | 13 | `affairs`, `amtl`, `boxes`, `conversation`, `crofoot`, `fertility`, `fish`, `hurricane`, `mortgage`, `panda_nuts`, `reading`, `soccer`, `toy` |
| [DiscoveryBench](https://huggingface.co/datasets/allenai/discoverybench) | 6 | `archaeology`, `nls_incarceration`, `nls_ses`, `requirements_engineering_for_ML_enabled_systems`, `worldbank_education_gdp`, `worldbank_education_gdp_indicators` |

Prepared tasks are written to `datasets/<benchmark>/<task_id>/`, where `<benchmark>` is `bixbench`, `blade`, or `discoverybench`. For example, `bix-52` becomes `datasets/bixbench/bix-52/`.

## Data preparation

Download the original benchmark files using the commands in the main [README](../README.md#data-preparation-and-processing). Then run these commands from the repository root to prepare the paper's selection:

```bash
python3 scripts/prepare_bixbench_tasks.py --task-list datasets/paper_tasks.json
python3 scripts/prepare_blade_tasks.py --task-list datasets/paper_tasks.json
python3 scripts/prepare_discoverybench_tasks.py --task-list datasets/paper_tasks.json
```

| Benchmark | Expected source directory | Preparation script |
| --- | --- | --- |
| BixBench | `bixbench/verified50/` and `bixbench/full/` | [prepare_bixbench_tasks.py](../scripts/prepare_bixbench_tasks.py) |
| BLADE | `blade/<task_id>/` | [prepare_blade_tasks.py](../scripts/prepare_blade_tasks.py) |
| DiscoveryBench | `discoverybench/<task_id>/` | [prepare_discoverybench_tasks.py](../scripts/prepare_discoverybench_tasks.py) |

The `--task-list` option selects the IDs for the corresponding benchmark and rejects missing requested IDs before conversion. Omit it to process all available tasks. The scripts preserve existing output directories; use `--output-dir` to select a fresh directory if you previously prepared additional tasks and need exactly the paper's selection.

### BixBench extraction

Verified-50 contains question-level records, which are converted into dataset-level open-ended tasks by [prepare_bixbench_tasks.py](../scripts/prepare_bixbench_tasks.py):

1. Deduplicate records by `capsule_uuid` and group capsules by their `short_id` (`bix-*`).
2. Select the 21 short IDs listed under `bixbench` in [paper_tasks.json](paper_tasks.json).
3. Extract data only from each archive's `CapsuleData-*` directories. If multiple capsules share a short ID, keep their files under separate `capsule_<uuid>/` subdirectories.

The full BixBench metadata is used only to cross-check capsule short IDs. Original questions, target hypotheses, and answers are excluded from the task packet.

## Task bundle format

```text
datasets/<benchmark>/<task_id>/
  data files...
  task_packet.json
```

Each task packet contains:

| Field | Contents |
| --- | --- |
| `task_id` | The task directory name |
| `dataset_paths` | Relative paths to the task's data files |
| `column_metadata` | Column names, inferred types, source files, and available column descriptions |
| `budget` | Defaults to 40 experiments and 90 minutes |

Source data remain subject to the original benchmark licenses.
