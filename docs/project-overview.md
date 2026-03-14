# Project Overview

Date: 2026-03-14
Active branch: `agentv4`

## 1. Repo objective

This repository should be treated as a paper-first offline research codebase:

- canonical EduBench loading
- deterministic shared-8 benchmark splits
- traceable per-sample predictions
- explicit baseline vs diagnostic system modes
- CPU-side recomputation of summaries from saved predictions

## 2. Current state after repo correction

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
3. `experiment_runner.py`
   - shared artifact writing for serial and parallel runs
4. `evaluator.py`
   - summary recomputation from saved predictions
   - optional post-hoc judge

## 3. What is intentionally secondary

The API/frontend path is not the main project story right now.

- `core/agent.py` is incomplete.
- `api/routes/chat.py` expects a helper that does not exist.
- `frontend/` should be treated as post-experiment work.

That is a deliberate priority choice, not an oversight: benchmark stability matters more than chat-serving polish.

## 4. Immediate next work after correction

After the correction pass, the next phase should focus on the final `1B -> 7B` adaptive cascade defined in `docs/02-final-project-implementation-spec.md`, not on product refactoring.
