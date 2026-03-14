# Pangu Offline Research Workspace

`/opt/pangu/pangu` 现在的主目标是一个**离线、可追踪、可复现实验**的教育 Agent 代码库，不是产品化聊天服务。

## 当前主线

- 共享主基准只使用 EduBench shared-8:
  - `Q&A`, `AG`, `EC`, `IP`, `PCC`, `PLS`, `QG`, `TMG`
- `ES` 被降级为补充任务，不进入主双语表。
- 离线实验入口优先于 API / frontend。
- 所有运行都应保存：
  - prediction JSONL
  - trace JSONL
  - summary JSON
  - optional judge cache

## 目录重点

```text
/opt/pangu/pangu
├── core/                  # 共享 Prompt 与核心逻辑
├── docs/                  # 研究规格与项目说明
├── outputs/
│   ├── predictions/       # 每次运行的逐样本预测
│   ├── summaries/         # 每次运行的汇总 JSON
│   ├── traces/            # 每次运行的路由追踪
│   ├── eval_cache/        # 可复用 judge 缓存
│   └── results/           # 历史遗留结果
├── runtime/               # 本地数据库、日志、密钥
├── config.py              # 可复现配置
├── data_loader.py         # Canonical EduBench loader
├── difficulty_decision.py # rule_v2 baseline router
├── inference_engine.py    # 系统模式编排与模型调用
├── experiment_runner.py   # 单进程/并行共享运行器
├── evaluator.py           # 预测后评估与 summary 重算
├── main.py                # 单进程实验入口
├── main_parallel.py       # 并行实验入口
└── run_server.py          # 遗留 API 入口
```

## 离线实验运行

单进程：

```bash
cd /opt/pangu/pangu
python main.py --system 7b_only --lang zh --split dev
python main.py --system cascade_final --lang zh --split test
```

并行：

```bash
cd /opt/pangu/pangu
python main_parallel.py --system rule_v2 --lang zh --split test --max-workers 4
python main_parallel.py --system 1b_only --lang en --split test --max-workers 4
```

可用系统名：

- `rule_v2`
- `current_v3`
- `1b_only`
- `7b_only`
- `cascade_final`

如果不加 `--do-judge`，summary 会明确标记为 `diagnostic only`，避免把未评估结果误当成论文结论。

## 预测后重算评估

模型预测保存后，可以不重新跑 GPU，直接重算 summary，或者补做可选 judge：

```bash
cd /opt/pangu/pangu
python evaluator.py --predictions outputs/predictions/<run>.jsonl
python evaluator.py --predictions outputs/predictions/<run>.jsonl --do-judge
```

## 路径约定

- 数据集根目录：`/opt/pangu/EduBench/data/all_data`
- 1B 模型路径：`/opt/pangu/openPangu-Embedded-1B-V1.1`
- 7B 模型路径：`/opt/pangu/openPangu-Embedded-7B-V1.1`
- judge 密钥优先读取环境变量 `GPT5_API_KEY`，否则读取 `runtime/secrets/GPT-key`

## API / Frontend 状态

- `core/agent.py` 仍是不完整状态。
- `api/routes/chat.py` 依赖缺失的 `get_agent_core`。
- `frontend/app.py` 不应阻塞离线实验。

当前结论很直接：**先稳定离线 benchmark，再回头修 API/frontend。**

## 文档入口

- `docs/01-repo-correction-spec.md`
- `docs/02-final-project-implementation-spec.md`
- `docs/03-paper-experiment-spec.md`
- `docs/project-overview.md`
