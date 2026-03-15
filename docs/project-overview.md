# Project Overview

Date: 2026-03-14
Active branch: `agentv4`

## 1. Repo objective

This repository should be treated as a paper-first offline research codebase:

- canonical EduBench loading
- deterministic shared-8 benchmark splits
- traceable per-sample predictions
- calibrated `1B -> 7B` cascade routing
- prompt-specialized `7B` refinement without fine-tuning
- explicit baseline vs diagnostic system modes
- CPU-side recomputation of summaries from saved predictions

## 2. Current state after final implementation

The important offline path is now:

1. `data_loader.py`
   - canonical prompt construction
   - stable `sample_id`
   - deterministic task-stratified splits
2. `inference_engine.py`
   - `rule_v2`
   - `current_v3`
   - `1b_only`
   - `7b_only`
   - `cascade_final`
   - `cascade_no_calibrator`
   - `cascade_no_specialist_prompt`
   - `cascade_no_draft_conditioning`
   - normalized request -> router -> risk -> specialist -> trace flow
3. `core/`
   - `schemas.py`
   - `request_normalizer.py`
   - `expert_router.py`
   - `risk_calibrator.py`
   - `route_trace.py`
   - `prompting/` for router/specialist/repair/self-check prompt assembly
4. `services/`
   - `model_clients.py` for local vLLM access
   - `output_parser.py` for router/prediction normalization
   - `result_store.py` for predictions/traces/summaries
5. `evaluation/`
   - `metrics.py`
   - `judge.py`
   - `summarize.py`
6. `experiment_runner.py`
   - shared artifact writing for serial and parallel runs
7. `evaluator.py`
   - summary recomputation from saved predictions
   - optional post-hoc judge

## 3. Runtime notes verified on 2026-03-14

- `7B` vLLM replicas are currently reachable on ports `8000`, `8001`, `8002`, and `8003`.
- The configured `1B` endpoint `172.17.0.1:1040` is not currently serving.
- The final cascade now degrades safely when `1B` is unavailable:
  - the router stage records the endpoint error
  - calibrated risk forces escalation
  - `7B` still produces a valid final artifact
- `7b_only`, `cascade_final`, and `evaluator.py --predictions ...` were live-tested successfully.

## 4. What is intentionally secondary

The API/frontend path is not the main project story right now.

- `core/agent.py` is incomplete.
- `api/routes/chat.py` expects a helper that does not exist.
- `frontend/` should be treated as post-experiment work.

That is a deliberate priority choice, not an oversight: benchmark stability matters more than chat-serving polish.
