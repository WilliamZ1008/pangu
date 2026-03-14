# AgentV4 Final Paper Architecture

Date: 2026-03-13  
Branch baseline: `agentv4`

## 1. Final Decision

最终版本不建议做成“纯 1B→7B 级联”或“纯多 7B 学科 MoA”。

我建议你把最后一版项目定为：

**Pangu-ACE: Adaptive Cascaded Experts for Education**

中文可表述为：

**盘古教育自适应级联专家 Agent**

它的核心不是 token-level speculative decoding，而是**sample-level semantic cascade**：

1. `1B` 负责首轮快速回答、任务识别、风险估计、结构约束检查。
2. 只有在高风险样本上，才把 `1B draft` 交给 `7B specialist` 做深推理与修正。
3. `7B` 不是一个统一 Prompt，而是**任务族专家 + 学科适配器**。
4. 工具链、记忆、会话能力保留为系统能力，但**论文主创新聚焦在“自适应级联 + 教育专家路由”**。

这会是你这套项目里最稳、最像论文、也最符合现有代码资产的一版。

## 2. Why This Final Version

你提出的两个方向都对，但都不应该原样作为最终版本。

### 2.1 Why not pure Idea 1

纯 1B + 7B Cascade 的优点是：

- 效率故事非常强
- 硬件成本清晰
- 和你当前 `Fast -> Evaluate -> Slow` 路线自然衔接

但如果只做“通用级联”，审稿人很容易说这只是 FrugalGPT 式工程迁移，**教育特异性不够强**。

### 2.2 Why not pure Idea 2

纯“Math Expert / Chinese Expert / English Expert”多 7B MoA 的问题是：

- EduBench 的异质性**主要不是学科异质性，而是任务形态异质性**
- `AG / PCC / PLS / QG / TMG` 这类任务，按学科分专家并不是最强切分方式
- 多 7B 常驻会明显提高资源占用与延迟
- 如果默认多专家聚合，论文容易变成“Prompt routing demo”，效率故事反而变弱

### 2.3 Why the hybrid is best

最终版应当把两个想法融合，但主次要分清：

- **主线创新**：`1B -> calibrated routing -> 7B specialist refinement`
- **次线增强**：`7B` 侧做专家化，但按**任务族**组织，学科作为适配维度，而不是唯一维度

所以最终系统不是“MoA 替代 Cascade”，而是：

**Cascade 是主架构，Experts 是 7B 层内部的能力组织方式。**

## 3. Current Repo Reality You Must Respect

在 `/opt/pangu/pangu` 和 `/opt/pangu/EduBench` 的当前状态下，最终设计必须建立在这些事实之上：

### 3.1 Existing code already points to dynamic routing

当前仓库已经有：

- `difficulty_decision.py`
- `inference_engine.py`
- `main.py`
- `main_parallel.py`
- `core/agent.py`
- `core/prompts.py`
- `core/tools/*`
- `services/session_manager.py`

也就是说，你不是从零开始，而是从：

**规则路由 -> 元认知路由原型 -> 并行评测原型**

继续往前走。

### 3.2 Current AgentV3 has a clear failure mode

当前结果里最重要的事实不是“已经成功”，而是：

- `summary_parallel_4x2_20260312_152027.json` 显示 `6600` 条样本上 `slow_trigger_rate = 99.56%`
- 当前 `7B self-eval` 基本上把几乎所有请求都升级为慢思考

这说明当前版本如果直接写论文，会被质疑：

- 元认知模块没有真正学会“节流”
- 系统没有形成 latency-accuracy Pareto improvement
- 路由器只是在“形式上存在”，没有在“效用上成立”

所以最终版的第一目标不是加更多模块，而是**把路由从“几乎全升高配”改成“真正有选择地升级”**。

### 3.3 Prompt-task mismatch is already visible

从保存的样本看，当前系统存在明显 prompt 错配：

- `question_generation` 样本出现与 ground truth 不一致的“成语题模板化生成”
- 说明任务识别、Prompt 绑定、输出结构控制还没有完全对齐

因此最终版必须把 Prompt 系统从 `inference_engine.py` 里剥离出来，做成**显式任务模板管理器**。

### 3.4 Dataset path and split must be corrected

你口头写的是 `/opt/EduBench`，但当前机器上真实路径是：

`/opt/pangu/EduBench`

更重要的是，本地数据并不完全对称：

- `zh_data`: 8 个 `jsonl` 主任务 + 一个特殊 `ES.py`
- `en_data`: 9 个 `jsonl` 任务

当前统计如下：

| Split | Count |
|---|---:|
| `zh_data` main jsonl total | `7793` |
| `en_data` main jsonl total | `9163` |
| overall | `16956` |

所以论文主实验最干净的做法是：

- **主表使用中英共享的 8 个任务**
- `zh ES` 只作为补充实验，不放进主表

### 3.5 You already have the right model assets

机器上已存在：

- `/opt/pangu/openPangu-Embedded-1B-V1.1`
- `/opt/pangu/openPangu-Embedded-7B-V1.1`

并且现有脚本已经证明：

- `7B` 可以用 `2` 张卡做 `TP=2`
- 机器也支持 `4x2` 的并行 7B 服务

这意味着你的最终版完全可以做出：

- 最小部署版：`1B x 1 card + 7B x 2 cards`
- 研究版：`1B + 3 个 7B specialist`

## 4. Final Architecture

## 4.1 System Name

**Pangu-ACE**

Full name:

**Adaptive Cascaded Experts for Efficient Educational Reasoning**

## 4.2 Core Pipeline

```text
User Query / EduBench Sample
        ↓
Request Normalizer
        ↓
Task + Subject Parser
        ↓
1B Fast Tutor-Router
  - quick draft answer
  - task-family prediction
  - confidence / uncertainty estimate
  - output schema check
  - tool-needed hint
        ↓
Risk Calibrator
        ↓
 ┌──────────────────────────────┬─────────────────────────────────┐
 │ low risk                     │ high risk                       │
 │ return 1B result directly    │ send draft to 7B specialist     │
 └──────────────────────────────┴─────────────────────────────────┘
                                         ↓
                             7B Specialist Refinement
                             - Reasoning Expert
                             - Assessment Expert
                             - Planning Expert
                             + subject adapter
                                         ↓
                             Validator / Tool / Formatter
                                         ↓
                               Final Educational Answer
                                         ↓
                           Route Trace + Metrics + Logging
```

## 4.3 The key idea

最终版的关键不是让 `1B` 和 `7B` 各回答一次再投票，而是：

**让 1B 先做“低成本、可放行、可升级”的前置决策。**

当样本被升级到 `7B` 时，`7B` 不是从零开始，而是读取：

- 原始问题
- `1B draft`
- `1B` 给出的不确定性理由
- 任务输出格式要求
- 所属任务族和学科信息

也就是说，`7B` 做的是**draft-conditioned specialist refinement**，不是盲重算。

这会比现在的：

`7B fast -> 7B self-eval -> 7B slow -> 7B concise`

更合理，也更容易打出效率结果。

## 5. Core Modules

## 5.1 Request Normalizer

职责：

- 统一 API 请求与 EduBench 样本格式
- 从 `question / prompt / metadata` 中抽出标准字段
- 形成统一 schema：

```json
{
  "task_type": "...",
  "task_family": "...",
  "subject": "...",
  "education_level": "...",
  "lang": "zh|en",
  "question": "...",
  "expected_output_format": "free_text|json|score|plan|question_set",
  "explanation_level": "brief|detailed"
}
```

为什么必须做：

- 当前 `DataLoader` 虽然已经统一了部分字段，但路由层和 Prompt 层还没有共享同一个结构化输入
- 最终版如果没有统一 schema，Prompt 错配问题还会反复出现

## 5.2 1B Fast Tutor-Router

这是最终版最重要的新模块。

### 5.2.1 1B should output structured JSON, not plain text only

`1B` 单次推理建议输出：

```json
{
  "task_family": "reasoning|assessment|planning",
  "subject": "math|chinese|english|general",
  "draft_answer": "...",
  "confidence_label": "high|medium|low",
  "confidence_score": 0.0,
  "reason_for_uncertainty": "...",
  "format_ok": true,
  "needs_tool": false,
  "needs_7b": false
}
```

### 5.2.2 Why 1B is not just a weak model

在这个系统里，`1B` 的作用不是“尽量和 7B 一样强”，而是：

- 过滤简单样本
- 发现格式风险
- 提供低成本草稿
- 为 7B 提供编辑起点

也就是说，`1B` 是：

**Fast Tutor + Router + Draft Generator**

### 5.2.3 Why not token-level speculative decoding

不建议把最终论文主线放在真正的 token speculative decoding 上，原因有三点：

1. 你当前工程是 request-level agent，不是底层解码引擎研究项目
2. Ascend + vLLM + Pangu 的 token-level speculative 改造成本高、调试风险大
3. 审稿时教育创新会被底层系统工程细节冲淡

所以最终版要做的是：

**semantic cascade, not low-level speculative decoding**

这更稳，也更符合你当前分支结构。

## 5.3 Risk Calibrator

这部分决定论文能不能成立。

当前版本最大问题就是“自评之后几乎全进 slow”。最终版必须把路由从单一标签判断升级为**校准式风险估计**。

### 5.3.1 Risk signals

建议风险分数由以下信号组成：

- `1B confidence_score`
- `confidence_label`
- 输出是否满足目标 schema
- 文本长度是否异常
- 是否触发数学 / 公式 / 多步规划信号
- 是否检测到“无法确定 / 需要更多信息 / 可能”等不确定语言
- 若 vLLM 可拿到 `logprobs`，加入平均 token entropy
- 任务先验风险 `task_prior`

### 5.3.2 Risk function

可直接在文档与代码中使用如下形式：

```text
risk(x) =
  a * low_confidence
+ b * format_error
+ c * entropy_signal
+ d * task_prior
+ e * tool_requirement
+ f * length_anomaly
```

然后按任务族使用不同阈值：

```text
if risk < tau_family:
    accept_1b
else:
    escalate_to_7b
```

### 5.3.3 What should be calibrated

建议不要用一个全局阈值，而是至少按三类任务族校准：

- `reasoning`
- `assessment`
- `planning`

因为：

- `Q&A / EC / IP` 可接受更多 `1B direct accept`
- `AG / ES` 更看重结构与反馈质量
- `PCC / PLS / QG / TMG` 更看重完整性与教育可用性

### 5.3.4 Paper value of this module

这一层是你能从“普通级联工程”变成“可发表系统”的关键点：

- 不是简单小模型先试一下
- 而是**经过校准的元认知风险路由**

这比当前的三分类自评标签更可信、更可分析。

## 5.4 7B Specialist Layer

最终版不建议做成 3 个完全独立训练的专家模型，而建议做成：

**同一 7B 权重 + 多专家服务角色 + Prompt adapter**

这样最符合你当前资源与工程能力。

### 5.4.1 Recommended task-family experts

| Expert | Main tasks | Responsibility |
|---|---|---|
| `Reasoning Expert` | `Q&A`, `EC`, `IP` | 解题、纠错、启发式思路生成 |
| `Assessment Expert` | `AG`, optional `ES` | 评分、反馈、解释、 rubric 对齐 |
| `Planning Expert` | `PCC`, `PLS`, `QG`, `TMG` | 路径规划、内容设计、题目生成、教学素材生成 |

### 5.4.2 Subject adapters

每个 expert 再叠加轻量学科适配前缀：

- `Math adapter`
- `Chinese adapter`
- `English adapter`
- `General adapter`

所以最终不是“学科专家替代任务专家”，而是：

**任务专家为主，学科适配为辅**

这是比你原始 Idea 2 更适合 EduBench 的设计。

### 5.4.3 When to use dual experts

不建议默认多专家聚合。

只有下面两类样本才允许双专家：

- `subject` 识别不明确且任务开放度高
- `1B` 与 `7B single expert` 输出结构存在明显冲突

默认路径仍然应是：

**single specialist**

否则你的效率故事会被自己破坏。

## 5.5 Prompt System

最终版必须把 Prompt 从 `inference_engine.py` 中彻底抽离。

### 5.5.1 Prompt dimensions

Prompt 至少按四个维度组合：

- `task_family`
- `task_type`
- `subject`
- `mode` (`fast`, `refine`, `judge`, `format`)

### 5.5.2 Prompt design principle

Prompt 不应该再写成“一个长模板包打天下”，而应当显式区分：

- objective QA
- grading / correction
- planning / generation

### 5.5.3 Output contract

每类任务都要有明确输出契约：

- `Q&A`: direct answer + concise explanation
- `AG`: score + evidence + personalized feedback
- `EC`: error list + corrected answer + explanation
- `PCC / PLS`: staged plan + student-specific recommendations
- `QG`: question + answer + rationale
- `TMG`: objective + key points + activity design

这样做的直接收益是：

- 减少错配
- 提升结构化有效率
- 让评测更容易自动化

## 5.6 Tool Layer

工具不是论文主创新，但应该保留成“边际增益模块”。

建议策略：

- `math / physics / formula-heavy` 问题允许 `calculator`、`sympy_solver`
- `AG / PCC / PLS / QG / TMG` 优先走 schema validator，不默认走数学工具
- 工具触发本身也应纳入 route trace

论文里可以把它写成：

**task-aware auxiliary tool invocation**

而不是主贡献。

## 5.7 Memory and Profile

当前仓库里已有 memory、session、user profile。

建议最终版处理方式：

- 产品系统中保留
- 论文主实验中默认关闭或弱化

原因很简单：

- EduBench 主体是单轮 benchmark
- 如果把记忆能力写成主创新，实验会被 benchmark 支撑不足拖累

所以论文主线不要写成“记忆型教育 agent”，而应写成：

**高效、自适应、专家化的教育推理系统**

## 6. Deployment Topology

## 6.1 Minimal publishable deployment

最推荐你论文里写这一版：

- `GPU 0`: `1B Fast Tutor-Router`
- `GPU 1-2`: `7B Specialist`

特点：

- 成本最清楚
- 和你的原始设想完全对齐
- 最容易做 latency 对比

## 6.2 Full research deployment on current machine

如果按当前 8 卡机器做研究版，可以部署为：

- `GPU 0`: `1B Router`
- `GPU 1`: reserve / telemetry / optional judge / warm standby
- `GPU 2-3`: `7B Reasoning Expert`
- `GPU 4-5`: `7B Assessment Expert`
- `GPU 6-7`: `7B Planning Expert`

这版适合做：

- 大规模离线评测
- 专家路由 ablation
- 吞吐和扩展性展示

## 6.3 Why this deployment is stronger than current 4x2

当前 `4x2` 脚本强调的是吞吐并行：

- 它适合批量评测
- 但不表达“架构创新”

最终版要表达的是：

- `1B` 负责前置筛选
- `7B` 负责高价值深推理
- `7B` 内部再按专家角色分工

这比“4 个相同 7B 并行跑”更适合写论文。

## 7. Required Repo Operations

这一节是最终落地必须做的操作说明。

## 7.1 Structural refactor

建议新增或拆分如下模块：

```text
/opt/pangu/pangu
├── core/
│   ├── routing/
│   │   ├── request_normalizer.py
│   │   ├── feature_extractor.py
│   │   ├── risk_calibrator.py
│   │   └── expert_selector.py
│   ├── prompts/
│   │   ├── prompt_manager.py
│   │   ├── fast_prompts.py
│   │   ├── specialist_prompts.py
│   │   └── output_contracts.py
│   └── tracing/
│       └── route_trace.py
├── services/
│   ├── model_clients.py
│   └── answer_validator.py
├── scripts/
│   ├── run_service_1b.sh
│   ├── run_service_7b_reasoning.sh
│   ├── run_service_7b_assessment.sh
│   └── run_service_7b_planning.sh
```

## 7.2 Files to modify

至少要重构：

- `config.py`
- `data_loader.py`
- `inference_engine.py`
- `main.py`
- `main_parallel.py`
- `core/prompts.py`
- `docs/evaluation-plan.md`

## 7.3 Config changes

`config.py` 里需要新增：

- `MODEL_NAME_1B`
- `MODEL_NAME_7B`
- `VLLM_API_URL_1B`
- `VLLM_API_URL_7B_REASONING`
- `VLLM_API_URL_7B_ASSESSMENT`
- `VLLM_API_URL_7B_PLANNING`
- `ROUTING_THRESHOLDS`
- `TASK_PRIORS`
- `ENABLE_ROUTE_TRACE`

## 7.4 Data loading changes

`data_loader.py` 需要做两件事：

1. 明确区分主实验任务与补充实验任务
2. 把 `zh ES.py` 从主 benchmark 流程里拆出去

建议主实验只跑：

- `Q&A`
- `AG`
- `EC`
- `IP`
- `PCC`
- `PLS`
- `QG`
- `TMG`

## 7.5 Inference changes

`inference_engine.py` 不应再同时承担：

- Prompt 拼接
- 直接推理
- 自评
- 路由决策
- 输出压缩

最终版应把它变成 orchestration 层，只负责：

- 调用 `1B`
- 调用 risk calibrator
- 调用 `7B specialist`
- 整合 trace

## 7.6 API changes

API 最终返回中建议加入 route metadata：

```json
{
  "model_path": "1b_direct|7b_reasoning|7b_assessment|7b_planning",
  "risk_score": 0.37,
  "escalated": false,
  "tool_used": [],
  "latency_ms": 812
}
```

这对论文图表和线上 debug 都很重要。

## 7.7 Output result schema

`outputs/results/*.jsonl` 最终必须统一字段：

- `task_type`
- `task_family`
- `subject`
- `lang`
- `route`
- `risk_score`
- `accepted_by_1b`
- `specialist_name`
- `prediction`
- `ground_truth`
- `latency`
- `tokens_1b`
- `tokens_7b`
- `format_valid`
- `tool_used`

这样后面做 paper table 才不会再返工。

## 8. Benchmark and Evaluation Design

## 8.1 Primary benchmark

主 benchmark 建议定义为：

**EduBench shared-8 tasks**

语言上建议分两张主表：

- `Table A`: `zh` shared-8
- `Table B`: `en` shared-8

原因：

- 你的模型是中文教育场景起家
- 中英文分开更容易讲清楚泛化能力

## 8.2 Development / Test protocol

建议采用：

- 每个任务、每个语言做分层采样
- `10%` 做路由阈值校准开发集
- `90%` 做正式测试

开发集的作用不是调 Prompt 到最优，而是：

- 调 `risk threshold`
- 调 `task prior`
- 调结构合法性检查规则

## 8.3 Baselines

最终论文至少应比较以下系统：

1. `AgentV2` rule-based fast/slow
2. `Current AgentV3` 7B self-eval dynamic routing
3. `1B only`
4. `7B specialist only` without cascade
5. `Pangu-ACE` final system

如果资源允许，再加一个：

6. `Pure subject-MoA 7B`

这个第 6 项不是为了最终胜出，而是为了证明：

**纯多专家并不如“级联 + 专家化”更优。**

## 8.4 Metrics

最终指标至少要有：

### Effectiveness

- overall accuracy / score
- per-task score
- format validity rate

### Efficiency

- average latency
- `P50 / P90 latency`
- `7B invocation rate`
- `GPU-seconds per sample` 或 token cost proxy

### Routing quality

- escalation precision
- escalation recall
- accepted-by-1B correctness
- route calibration curve

其中最重要的新指标是：

**7B invocation rate**

因为最终论文不是单纯比强，而是比：

**用更少 7B 深推理调用，拿到接近甚至更好的教育质量。**

## 8.5 Evaluation method

建议采用混合评测：

- 选择题、短答案、可判定题：规则指标 / exact match / schema match
- 开放生成题：LLM-as-a-judge + rubric

但当前仓库里的 `GPT5Judge` 已经出现 `404`，所以最终版文档必须明确：

### Judge strategy

优先级建议：

1. 使用稳定可复现的 judge API，并缓存全部评分结果
2. 若 API 不稳定，则主表先用规则指标 + 格式指标 + 人工抽样复核
3. 开放题单独给 judge table，不让 judge 成为整个实验的单点故障

## 9. Expected Results

下面不是承诺值，而是**合理目标区间**。

## 9.1 What you should target

相对当前 `7B-only dynamic router`，最终版应争取达到：

- `7B invocation rate`: 从接近 `100%` 降到 `35% ~ 60%`
- `average latency`: 降低 `55% ~ 75%`
- `format validity`: 提升 `10% ~ 20%`
- `overall score`: 持平到提升 `0% ~ 5%`

如果以你当前 `99.56%` 的 slow-trigger 原型做对比，论文里写：

**“average inference time reduced by 70%+ against the previous 7B-only self-evaluative pipeline while preserving or improving task quality”**

是有机会站住的。

## 9.2 Per-task expectation

| Task family | Expected effect |
|---|---|
| `Q&A / EC / IP` | 1B 放行率最高，延迟下降最明显 |
| `AG / ES` | 7B specialist 带来反馈质量与结构稳定性提升 |
| `PCC / PLS / QG / TMG` | 7B 触发率更高，但专家化 Prompt 会明显优于当前通用模板 |

## 9.3 What not to promise

不建议在文档里提前承诺：

- “所有任务都显著涨点”
- “一定超过所有闭源模型”
- “所有场景都能 70%+ 加速”

更合理的说法是：

- 在**平均层面**显著降低推理成本
- 在**结构化教育任务**上提升稳定性
- 在**简单与中等难度任务**上显著提高吞吐

## 10. Main Innovations to Write in the Paper

最终论文建议收敛为 4 个贡献点。

### Innovation 1

**教育任务上的 1B→7B 语义级联推理框架**

不是底层 speculative decoding，而是面向教育 agent 的 sample-level adaptive inference。

### Innovation 2

**经过校准的元认知路由器**

不是只靠一句“我有信心吗”，而是把：

- 自评信号
- 结构合法性
- 任务先验
- 输出异常

统一成风险估计。

### Innovation 3

**任务族专家化 + 学科适配的 7B specialist**

不是简单的“数学专家 / 语文专家 / 英语专家”三分法，而是更符合 EduBench 的：

- reasoning
- assessment
- planning

再叠加 subject adapter。

### Innovation 4

**可解释的 route trace 与 Pareto 分析**

每条样本都能分析：

- 为什么被 1B 接受
- 为什么被升级到 7B
- 升级后有没有真的改善

这对论文说服力非常重要。

## 11. Paper Framing

## 11.1 Title candidates

可选标题：

1. `Pangu-ACE: Adaptive Cascaded Experts for Efficient Educational Reasoning`
2. `Efficient Educational Agents via Metacognitive Cascaded Routing and Specialist Refinement`
3. `From Fast Tutors to Specialist Reasoners: A Cascaded Pangu Agent for EduBench`

## 11.2 Core claims

论文主 claim 建议写成：

- 你提出了一个教育场景下的轻量级自适应推理框架
- 它将小模型快速响应与大模型专家推理结合
- 它在 EduBench 上实现了更优的 accuracy-efficiency trade-off

## 11.3 Recommended figures

论文最值得画的图：

1. 系统架构图
2. 路由分布图：1B 接受 vs 7B 升级
3. 不同任务族的 latency 柱状图
4. Accuracy-Latency Pareto 曲线
5. 案例分析图：1B 错误被 7B specialist 修正

## 11.4 Recommended tables

必须至少有 4 张表：

1. 主结果表：overall + per-task
2. 效率表：latency / 7B invocation / throughput
3. 消融表：去掉 calibrator、去掉 specialist、去掉 draft conditioning
4. Case study 表：典型成功与失败案例

## 12. What Should Not Be the Main Story

下面这些内容可以保留，但不要当作论文主线：

- 长期记忆
- 用户画像
- 前端界面
- 普通 ReAct 工具链
- 纯多轮会话能力
- token-level speculative decoding 工程细节

原因不是它们不重要，而是：

**它们不足以支撑你这篇 paper 的核心实验闭环。**

你的主线必须足够单一：

**Adaptive Educational Inference**

## 13. Final Execution Order

最终落地顺序建议严格如下：

1. 修正数据路径、任务集合和输出 schema
2. 把 Prompt 系统从 `inference_engine.py` 中拆出
3. 上线 `1B Fast Tutor-Router`
4. 建立 risk calibrator 和 route trace
5. 把 `7B` 改造成 task-family specialists
6. 跑 shared-8 的 dev set 做阈值校准
7. 跑 shared-8 的 zh / en 主实验
8. 跑 ablation
9. 跑 case study 和可视化
10. 最后再接回 API / frontend 展示版

## 14. Final Recommendation in One Sentence

你的最后一版项目，应该定为：

**以 1B 为前置快速导师与路由器、以 7B 为任务族专家执行器、以校准式元认知风险估计为核心调度机制的 Pangu-ACE 教育 Agent。**

这比“纯级联”更有教育特异性，比“纯 MoA”更有资源优势，也比你当前 `agentv4` 原型更像一篇真正可以写进 paper 的系统工作。
