# Final Project Implementation Spec

Use this document second. It defines the final deliverable that should be built after the repository has been corrected by `01-repo-correction-spec.md`.

## Scope Decision

Build a **paper-first offline research system**, not a product-first chatbot platform.

The final system should be:

- a `1B -> 7B` adaptive educational cascade
- driven by calibrated routing, not by fixed rules
- specialized by task family through prompts, not by multiple fine-tuned experts
- fully traceable at the sample level
- runnable on the current machine without retraining

## Important Rebuttal

Do **not** start by deploying three separate `7B` specialist services.

That is optional optimization, not the first stable milestone.

The first final version should use:

- one `1B` service endpoint
- one `7B` service endpoint
- specialist behavior controlled by prompt adapters

Only after this version is stable should you consider duplicating the same `7B` weights behind multiple ports for throughput experiments.

## Final System Definition

The final method is:

1. normalize an EduBench sample into a canonical request
2. ask `1B` for:
   - task-family prediction
   - subject prediction
   - draft answer
   - confidence estimate
   - structural risk hints
3. compute a calibrated risk score
4. if low risk:
   - accept the `1B` answer
5. if high risk:
   - select a `7B` specialist role
   - refine the answer using the original request plus the `1B` draft
6. validate the final output format
7. save the full route trace

## Final Non-Goals

These are out of scope for the final version:

- retraining or fine-tuning Pangu
- multi-agent debate
- long-horizon memory as a main paper contribution
- ReAct tool use as the main reasoning loop
- full product backend refactor before experiments
- token-level speculative decoding

## Required Files To Modify

These existing files must change:

- `/opt/pangu/pangu/config.py`
- `/opt/pangu/pangu/data_loader.py`
- `/opt/pangu/pangu/difficulty_decision.py`
- `/opt/pangu/pangu/inference_engine.py`
- `/opt/pangu/pangu/main.py`
- `/opt/pangu/pangu/main_parallel.py`
- `/opt/pangu/pangu/evaluator.py`
- `/opt/pangu/pangu/core/prompts.py`
- `/opt/pangu/pangu/scripts/run_service_7b.sh`
- `/opt/pangu/pangu/README.md`

## Required Files To Add

Add the following files. Keep names stable so the experiment document can assume them later.

### New Core Files

- `/opt/pangu/pangu/core/schemas.py`
- `/opt/pangu/pangu/core/request_normalizer.py`
- `/opt/pangu/pangu/core/expert_router.py`
- `/opt/pangu/pangu/core/risk_calibrator.py`
- `/opt/pangu/pangu/core/route_trace.py`

### New Prompting Files

- `/opt/pangu/pangu/core/prompting/__init__.py`
- `/opt/pangu/pangu/core/prompting/prompt_manager.py`
- `/opt/pangu/pangu/core/prompting/task_templates.py`
- `/opt/pangu/pangu/core/prompting/output_contracts.py`

### New Service Files

- `/opt/pangu/pangu/services/model_clients.py`
- `/opt/pangu/pangu/services/output_parser.py`
- `/opt/pangu/pangu/services/result_store.py`

### New Evaluation Files

- `/opt/pangu/pangu/evaluation/__init__.py`
- `/opt/pangu/pangu/evaluation/metrics.py`
- `/opt/pangu/pangu/evaluation/judge.py`
- `/opt/pangu/pangu/evaluation/summarize.py`

### New Script Files

- `/opt/pangu/pangu/scripts/run_service_1b.sh`
- `/opt/pangu/pangu/scripts/run_eval.sh`
- `/opt/pangu/pangu/scripts/run_eval_parallel.sh`
- `/opt/pangu/pangu/scripts/run_calibration.sh`

## Target Directory Shape

After implementation, the important part of the repository should look like this:

```text
/opt/pangu/pangu
├── config.py
├── data_loader.py
├── inference_engine.py
├── main.py
├── main_parallel.py
├── evaluator.py
├── evaluation/
│   ├── __init__.py
│   ├── metrics.py
│   ├── judge.py
│   └── summarize.py
├── core/
│   ├── schemas.py
│   ├── request_normalizer.py
│   ├── expert_router.py
│   ├── risk_calibrator.py
│   ├── route_trace.py
│   ├── prompts.py
│   └── prompting/
│       ├── __init__.py
│       ├── prompt_manager.py
│       ├── task_templates.py
│       └── output_contracts.py
├── services/
│   ├── model_clients.py
│   ├── output_parser.py
│   └── result_store.py
└── scripts/
    ├── run_service_1b.sh
    ├── run_service_7b.sh
    ├── run_eval.sh
    ├── run_eval_parallel.sh
    └── run_calibration.sh
```

## Main Data Structures

### `core/schemas.py`

Main classes:

- `NormalizedSample`
- `RouterOutput`
- `RiskFeatures`
- `RouteTrace`
- `InferenceResult`

Required fields:

`NormalizedSample`

- `sample_id`
- `task_key`
- `task_type`
- `task_family`
- `subject`
- `education_level`
- `lang`
- `question`
- `prompt_text`
- `expected_output_format`
- `ground_truth`
- `metadata`

`RouterOutput`

- `predicted_task_family`
- `predicted_subject`
- `draft_answer`
- `confidence_label`
- `confidence_score`
- `format_signals`
- `tool_hint`
- `raw_text`
- `parse_ok`

`RiskFeatures`

- `confidence_score`
- `low_confidence_flag`
- `format_error_flag`
- `length_anomaly_flag`
- `uncertainty_phrase_flag`
- `task_prior`
- `subject_mismatch_flag`

`RouteTrace`

- `sample_id`
- `system_name`
- `accepted_by_1b`
- `risk_score`
- `risk_threshold`
- `specialist_name`
- `format_valid`
- `latency_1b`
- `latency_7b`
- `tokens_1b`
- `tokens_7b`
- `notes`

## File-by-File Responsibilities

### `/opt/pangu/pangu/core/request_normalizer.py`

Main class:

- `RequestNormalizer`

Required public methods:

- `normalize_data_item(data_item) -> NormalizedSample`
- `build_primary_benchmark_sample(raw_item, task_key, lang, source_file, line_index) -> NormalizedSample`

Responsibilities:

- convert task-specific EduBench rows into one canonical schema
- decide whether to trust raw question text or reconstruct prompt text
- map each task to:
  - `task_type`
  - `task_family`
  - `expected_output_format`

### `/opt/pangu/pangu/core/prompting/task_templates.py`

Contents:

- task-family prompt templates
- task-type overrides
- subject adapters

Required template groups:

- `fast_router`
- `specialist_reasoning`
- `specialist_assessment`
- `specialist_planning`
- `format_repair`
- `self_check`

### `/opt/pangu/pangu/core/prompting/output_contracts.py`

Define output contracts for each task:

- `Q&A`: direct answer + short explanation
- `AG`: score + evidence + feedback
- `EC`: error list + corrected answer + explanation
- `IP`: structured hints, not full answer leakage where possible
- `PCC`: learning path + personalized suggestions
- `PLS`: student-specific learning content/tasks
- `QG`: generated question + answer + rationale
- `TMG`: objectives + key points + classroom activity design

Required helper:

- `get_output_contract(task_key)`

### `/opt/pangu/pangu/core/prompting/prompt_manager.py`

Main class:

- `PromptManager`

Required methods:

- `build_1b_router_prompt(sample)`
- `build_7b_specialist_prompt(sample, router_output, specialist_name)`
- `build_format_repair_prompt(sample, draft_output)`
- `build_rule_baseline_prompt(sample, mode)`

Responsibilities:

- all prompt assembly
- no prompt string should remain embedded in `inference_engine.py`

### `/opt/pangu/pangu/core/expert_router.py`

Main class:

- `ExpertRouter`

Required method:

- `select(sample, router_output) -> str`

Return values:

- `reasoning`
- `assessment`
- `planning`

Mapping:

- `Q&A`, `EC`, `IP` -> `reasoning`
- `AG` -> `assessment`
- `PCC`, `PLS`, `QG`, `TMG` -> `planning`

Keep `ES` out of the primary path.

### `/opt/pangu/pangu/core/risk_calibrator.py`

Main class:

- `RiskCalibrator`

Required methods:

- `extract_features(sample, router_output) -> RiskFeatures`
- `score(features) -> float`
- `should_escalate(sample, features, score) -> bool`

First stable version should use a transparent weighted formula, not a trained classifier.

Initial risk formula:

```text
risk =
  0.35 * low_confidence_flag +
  0.20 * format_error_flag +
  0.15 * uncertainty_phrase_flag +
  0.10 * length_anomaly_flag +
  0.20 * task_prior
```

Use per-family thresholds:

- `reasoning`: `0.45`
- `assessment`: `0.35`
- `planning`: `0.40`

These thresholds are starting points only. Calibrate them later on the dev split.

### `/opt/pangu/pangu/core/route_trace.py`

Main class:

- `RouteTracer`

Required methods:

- `start(sample, system_name)`
- `record_1b(...)`
- `record_risk(...)`
- `record_7b(...)`
- `finalize(...)`

Responsibilities:

- make every sample debuggable after the run
- produce JSON-serializable trace rows

### `/opt/pangu/pangu/services/model_clients.py`

Main classes:

- `VLLMClient`
- `ClientRegistry`

Required methods:

- `generate_text(prompt, endpoint, model_name, max_tokens, temperature)`
- `generate_json(prompt, endpoint, model_name, max_tokens, temperature)`

Responsibilities:

- all HTTP calls to vLLM
- retries and timeout handling
- no routing logic here

### `/opt/pangu/pangu/services/output_parser.py`

Main class:

- `OutputParser`

Required methods:

- `parse_router_output(text) -> RouterOutput`
- `validate_prediction(sample, prediction) -> tuple[bool, dict]`
- `repair_or_normalize(sample, prediction) -> dict`

Responsibilities:

- parse the `1B` structured output
- validate task-specific output shape
- normalize final answers into comparable structures

### `/opt/pangu/pangu/services/result_store.py`

Main class:

- `ResultStore`

Required methods:

- `save_predictions(run_name, rows)`
- `save_traces(run_name, traces)`
- `save_summary(run_name, summary)`

Responsibilities:

- consistent artifact paths
- zero experiment-specific ad hoc JSON dumping inside `main.py`

### `/opt/pangu/pangu/evaluation/metrics.py`

Main class:

- `MetricSuite`

Required methods:

- `score_prediction(sample, prediction, trace)`
- `aggregate(rows)`

Metrics to implement:

- `format_validity`
- task-aware rule metrics where possible
- `latency_avg`
- `latency_p50`
- `latency_p90`
- `accepted_by_1b_rate`
- `7b_invocation_rate`

### `/opt/pangu/pangu/evaluation/judge.py`

Main class:

- `JudgeRunner`

Required behavior:

- optional post-hoc judge only
- cache every request and response
- never block raw prediction generation

### `/opt/pangu/pangu/evaluation/summarize.py`

Main class:

- `SummaryBuilder`

Required outputs:

- overall summary JSON
- per-task summary JSON
- per-route summary JSON

## How Existing Files Should Be Reworked

### `/opt/pangu/pangu/inference_engine.py`

This file becomes the orchestration layer.

Main class:

- `InferenceEngine`

Required public methods:

- `run_rule_v2(sample)`
- `run_current_v3(sample)`
- `run_1b_only(sample)`
- `run_7b_only(sample)`
- `run_cascade_final(sample)`

What it should do:

- call the right model client
- call the prompt manager
- call the risk calibrator
- call the expert router
- produce `InferenceResult` and `RouteTrace`

What it should **not** do anymore:

- define inline task prompts
- parse dataset rows
- save files directly
- own evaluation logic

### `/opt/pangu/pangu/main.py`

This file becomes the single-process experiment runner.

Main class:

- `ExperimentRunner`

Required methods:

- `run(system_name, lang, split, do_judge=False)`
- `run_all(system_names, split_plan, do_judge=False)`

Responsibilities:

- load split
- iterate samples
- collect predictions and traces
- pass them to `ResultStore`
- pass outputs to `MetricSuite` and `SummaryBuilder`

### `/opt/pangu/pangu/main_parallel.py`

Keep it as a parallel wrapper around `ExperimentRunner`, not a separate logic path.

Requirements:

- same output schema as `main.py`
- same system names
- same trace schema
- same split semantics

### `/opt/pangu/pangu/evaluator.py`

Keep only as backward-compatible wrapper or thin delegate into `evaluation/judge.py`.

Do not let it remain the only evaluator implementation.

## New Scripts and Their Purpose

### `/opt/pangu/pangu/scripts/run_service_1b.sh`

Purpose:

- start one `1B` vLLM endpoint

Expected config:

- served model: `/opt/pangu/openPangu-Embedded-1B-V1.1`
- single-card or low-parallel deployment

### `/opt/pangu/pangu/scripts/run_service_7b.sh`

Purpose:

- keep one stable `7B` service endpoint for the final system

Do not split into multiple role-specific ports until the final system works with one `7B`.

### `/opt/pangu/pangu/scripts/run_calibration.sh`

Purpose:

- run dev-split experiments used to tune risk thresholds

### `/opt/pangu/pangu/scripts/run_eval.sh`

Purpose:

- run one full experiment in single-process mode

Expected interface:

```bash
python main.py --system cascade_final --lang zh --split test
```

### `/opt/pangu/pangu/scripts/run_eval_parallel.sh`

Purpose:

- run one full experiment in parallel mode using the same semantics as `run_eval.sh`

## Implementation Phases

### Phase 1: Foundation

Complete first:

- corrected loader
- canonical schemas
- prompt manager
- model client abstraction

Exit condition:

- `1b_only` and `7b_only` can run on a tiny sample set with correct output files

### Phase 2: Final Cascade Logic

Complete next:

- risk calibrator
- expert router
- route tracer
- `run_cascade_final`

Exit condition:

- the system can accept some samples directly from `1B`
- route traces are saved

### Phase 3: Evaluation Layer

Complete next:

- deterministic metrics
- summary builder
- judge cache

Exit condition:

- one experiment run produces predictions, traces, summaries, and optional judge cache

### Phase 4: Throughput

Complete only after the previous phases work:

- `main_parallel.py`
- optional duplicated `7B` services for throughput

### Phase 5: Demo Surface

Do last:

- API metadata exposure
- frontend integration
- README cleanup

## Final Output Contract For Saved Prediction Rows

Every final prediction row must contain at least:

- `sample_id`
- `system_name`
- `task_key`
- `task_type`
- `task_family`
- `subject`
- `lang`
- `route`
- `accepted_by_1b`
- `specialist_name`
- `risk_score`
- `prediction`
- `ground_truth`
- `format_valid`
- `latency_seconds`
- `tokens_1b`
- `tokens_7b`
- `judge_score` if available

## Definition of Done

The implementation stage is complete only when all of the following are true:

1. `1b_only`, `7b_only`, and `cascade_final` all run from the same batch runner.
2. Prompt definitions live outside `inference_engine.py`.
3. Every saved result row has a route trace.
4. `7B` role specialization is prompt-based and task-family-based.
5. The final system does not depend on API/frontend code.
6. The repository can run the experiment bundle from the third document without further structural refactoring.
