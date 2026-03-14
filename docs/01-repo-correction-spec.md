# Repo Correction Spec

Use this document first. Its purpose is to turn `/opt/pangu/pangu` from a partially working prototype into a trustworthy offline research codebase. Do not start final architecture work until everything here is true.

## Mission

The real project objective is:

- build a publishable education-agent system around Pangu
- evaluate it reproducibly on EduBench
- optimize the accuracy/efficiency tradeoff, not just raw response quality

The current repository is **not** ready for paper experiments. Several results already stored in `outputs/results/` are useful for diagnosis, but they are not trustworthy as final evidence.

## Repository Truth You Must Respect

- Code root: `/opt/pangu/pangu`
- Dataset root: `/opt/pangu/EduBench/data/all_data`
- Main paper benchmark should be the shared 8 tasks:
  - `Q&A`, `AG`, `EC`, `IP`, `PCC`, `PLS`, `QG`, `TMG`
- `ES` must be removed from the primary benchmark:
  - `zh_data` has no `ES.jsonl`; it has `ES.py`, which is a generation script, not benchmark data
  - `en_data` has `ES.jsonl`, but that asymmetry makes it unsuitable for the main bilingual table

## Critical Problems Already Found

These are factual problems in the current codebase. Treat them as bugs, not as design opinions.

1. `config.py` maps `ES` to `essay_scoring`, but EduBench `ES` means `emotional_support`.
2. `DEBUG_MODE = True` in `config.py`, so `DataLoader.load_all()` silently truncates the benchmark.
3. The saved `6600`-sample parallel result is a debug-truncated run, not a full-dataset run.
4. `data_loader.py` trusts `raw["question"]` too often. In multiple EduBench files, that field is a stale generation prompt and does **not** match the actual sample content.
5. English `PCC`, `PLS`, and `ES` are not parsed correctly because the loader mostly expects Chinese keys.
6. `DataItem` has no stable sample id, so result files cannot be traced back reliably.
7. `difficulty_decision.py` returns `both`, which is not a paper-grade route definition.
8. `inference_engine.py` mixes prompt templates, routing logic, self-evaluation, and model I/O in one file.
9. `self_evaluate()` parses labels by substring search in a brittle order and can misclassify messy outputs.
10. `core/agent.py` is incomplete, contains an invalid hardcoded import path, and does not define the API helper expected by `api/routes/chat.py`.
11. `GPT5Judge` is not reproducible enough to be the only evaluation path:
    - docs say GPT-5.4
    - `config.py` uses `gpt-5.3`
    - the API path has already failed before

## What Must Be True Before Final Implementation

You are done with this document only when the repository satisfies all of the following:

- the loader reads the intended benchmark without hidden truncation
- each sample has a stable canonical representation
- each result row can be traced to one dataset sample
- the baseline route logic is deterministic and explicitly named
- the current dynamic-router pipeline can be run for diagnosis without corrupt prompt binding
- evaluation can be recomputed from saved predictions without needing GPUs again
- API/frontend are clearly marked secondary and do not block offline experiments

## Priority Order

Follow this order exactly.

### Step 1: Correct `config.py`

File to change:

- `/opt/pangu/pangu/config.py`

Required changes:

- Set `DEBUG_MODE = False` by default.
- Add an explicit runtime flag or environment variable for debug sampling.
- Replace the incorrect `ES` mapping:
  - `ES -> emotional_support`
- Add explicit benchmark task groups:
  - `PRIMARY_TASK_KEYS = ["Q&A", "AG", "EC", "IP", "PCC", "PLS", "QG", "TMG"]`
  - `SUPPLEMENTARY_TASK_KEYS = ["ES"]`
- Add explicit model path config for both cascade tiers:
  - `MODEL_PATH_1B`
  - `MODEL_PATH_7B`
  - `MODEL_NAME_1B`
  - `MODEL_NAME_7B`
- Add explicit endpoint config:
  - `VLLM_API_URL_1B`
  - `VLLM_API_URL_7B`
- Add evaluation and artifact directories:
  - `OUTPUT_PREDICTION_DIR`
  - `OUTPUT_SUMMARY_DIR`
  - `OUTPUT_TRACE_DIR`
  - `OUTPUT_EVAL_CACHE_DIR`
- Add split config:
  - `DEV_RATIO = 0.1`
  - `RANDOM_SEED = 42`

Do not add many knobs. Add only values that affect reproducibility.

### Step 2: Rewrite the data contract in `data_loader.py`

File to change:

- `/opt/pangu/pangu/data_loader.py`

This is the most important correction in the whole repository.

Required changes:

- Add a stable `sample_id` field to `DataItem`.
- Add `task_key`, `task_family`, and `expected_output_format`.
- Sort file lists before loading.
- Stop using `raw["question"]` blindly as the model input.
- Build task prompts from canonical sample fields instead.
- Preserve raw fields only as metadata for debugging.
- Add explicit split support:
  - `load_primary_split(lang, split)`
  - `load_primary_all()`
  - `load_task_split(task_key, lang, split)`
- Exclude `zh_data/ES.py` from the primary benchmark path.
- Support English key variants for `PCC`, `PLS`, and `ES`.

### Canonical Prompt Rule

Use this rule:

- If the dataset field is clearly the real task prompt, use it.
- If the dataset field is a stale generation instruction, rebuild the prompt from structured fields.

Examples:

- `Q&A`, `EC`: using the direct question text is usually correct.
- `QG`, `TMG`, `PCC`, and some `AG` rows: do **not** trust `raw["question"]`; rebuild the prompt from `知识点`, `学生画像`, `问题`, `学生的答案`, `教学素材`, and similar structured fields.

### Ground Truth Rule

Ground truth must never come from the repository's top-level `answer` field by default, because in many EduBench files that field stores candidate model outputs rather than gold annotations.

Use task-specific gold extraction:

- `Q&A`: top-level `答案`
- `AG`: `评分`, `评分细节`, `个性化反馈`
- `EC`: `纠错后答案`, optionally `纠错说明`
- `IP`: `提供的思路`
- `PCC`: `学习路径规划建议`, `个性化意见生成`
- `PLS`: `个性化学习内容/任务`
- `QG`: `问题`, `提供的思路`, `答案`
- `TMG`: `教学素材`
- `ES` if later supported: `Emotional State Analysis`, `Comfort and Advice` or the Chinese equivalents

### Step 3: Make the baseline route deterministic

File to change:

- `/opt/pangu/pangu/difficulty_decision.py`

Keep this file, but demote it to a baseline-only component.

Required changes:

- Rename the behavior conceptually from "difficulty decision for the whole system" to "rule baseline router".
- Replace ambiguous `both` with an explicit baseline route name:
  - `fast`
  - `slow`
  - `slow_then_fast` if you insist on preserving the current behavior
- Return both route label and reason.
- Record the route as metadata in batch results.

Do not let this file remain part of the final proposed method. It is only a baseline.

### Step 4: Separate current dynamic routing from broken prompt binding

Files to change:

- `/opt/pangu/pangu/inference_engine.py`
- `/opt/pangu/pangu/core/prompts.py`

Immediate corrections required even before the final refactor:

- move task prompt strings out of method bodies
- make self-eval label parsing robust
- log the raw self-eval output
- record which prompt template was used
- stop returning only free-text blobs when structured outputs are expected

For the current self-eval parser:

- normalize output to lowercase
- extract the first valid label from a whitelist
- reject outputs containing multiple conflicting labels
- store a `parse_ok` flag

Do not try to make the current `7B fast -> 7B self-eval -> 7B slow -> 7B concise` pipeline the final paper system. Only keep it runnable as a diagnostic baseline.

### Step 5: Fix batch experiment entrypoints

Files to change:

- `/opt/pangu/pangu/main.py`
- `/opt/pangu/pangu/main_parallel.py`

Required changes:

- Make the run mode explicit:
  - `rule_v2`
  - `current_v3`
  - `1b_only`
  - `7b_only`
  - `cascade_final`
- Add explicit split arguments.
- Add explicit output file naming based on:
  - system
  - language
  - split
  - timestamp
- Write one JSONL prediction file plus one JSON summary file per run.
- Write one route-trace JSONL file per run.
- Never let `do_eval=False` silently produce a paper-looking summary without warning.

Each result row must include at least:

- `sample_id`
- `task_key`
- `task_type`
- `task_family`
- `lang`
- `route`
- `prediction`
- `ground_truth`
- `latency_seconds`
- `format_valid`
- `raw_model_outputs`

### Step 6: Downgrade API/frontend priority

Files to leave alone for now, except for documenting their status:

- `/opt/pangu/pangu/core/agent.py`
- `/opt/pangu/pangu/api/*`
- `/opt/pangu/pangu/frontend/app.py`

Reality:

- the API path is incomplete and currently broken
- the paper does not need it
- fixing it now burns time without improving the benchmark story

What to do instead:

- clearly mark API/frontend as post-experiment work
- only return to them after the offline paper pipeline is stable

If you do touch the API later, first fix:

- the invalid hardcoded path in `core/agent.py`
- the missing `get_agent_core`
- the mismatch between chat-serving schemas and offline batch inference

## Explicit Corrections to Existing Research Claims

Do not repeat these claims in the paper or README until they are revalidated:

- "full-dataset evaluation" based on the existing 6600-sample run
- "dynamic routing works" based on the current 99.56% slow-trigger output
- "question_generation prompt design is correct"
- "the API service is production-ready"

These claims are not currently supported by the repository state.

## Minimal Acceptance Tests For This Document

Before moving to the next document, verify all of the following:

1. Loading the primary benchmark returns the expected counts:
   - zh shared-8 total: `7793`
   - en shared-8 total: `8102`
2. The loader can print five canonical samples from different tasks without using stale prompts.
3. At least one corrected `QG` sample no longer collapses into the unrelated "成语" template.
4. The baseline rule runner produces explicit route labels without `both`.
5. The current dynamic baseline can run on a small split and save:
   - predictions
   - traces
   - self-eval raw outputs
6. Every saved row includes a stable `sample_id`.

## Rebuttals You Should Keep

These are deliberate contradictions to earlier repository ideas and should remain unless new evidence proves otherwise:

- Do **not** keep `ES` inside the main benchmark.
- Do **not** treat memory, tools, and frontend as the main paper story.
- Do **not** trust saved results generated before the loader fix.
- Do **not** spend more time polishing `core/agent.py` before the offline experiment path is stable.
- Do **not** keep prompt templates embedded in inference methods.

## Output of This Stage

When this document is fully executed, the repository should have:

- a trustworthy dataset interface
- a trustworthy baseline runner
- a trustworthy diagnostic current-V3 runner
- reproducible result artifacts
- a clean starting point for the final system in the next document
