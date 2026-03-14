# Paper Experiment Spec

Use this document third. It defines the experiment bundle that must be completed before you lose GPU time. The design goal is that once the predictions and traces are saved, you should be able to finish the paper later without rerunning the models.

## Core Principle

Run inference once, save everything, and make later analysis GPU-free.

For every experiment run, save all of the following:

- raw prediction JSONL
- route trace JSONL
- summary JSON
- optional judge cache
- per-task aggregate JSON

If you do this correctly, table changes later will only require CPU-side recomputation.

## Final Benchmark Definition

Use **shared-8 EduBench tasks only** for the main paper:

- `Q&A`
- `AG`
- `EC`
- `IP`
- `PCC`
- `PLS`
- `QG`
- `TMG`

Do not use `ES` in the main benchmark.

## Confirmed Sample Counts

Use these exact counts as sanity checks:

### Chinese shared-8

- `AG`: `931`
- `EC`: `620`
- `IP`: `1342`
- `PCC`: `568`
- `PLS`: `348`
- `Q&A`: `1306`
- `QG`: `1343`
- `TMG`: `1335`
- total: `7793`

### English shared-8

- `AG`: `1042`
- `EC`: `1301`
- `IP`: `1301`
- `PCC`: `252`
- `PLS`: `448`
- `Q&A`: `1285`
- `QG`: `1288`
- `TMG`: `1185`
- total: `8102`

## Fixed Split Plan

Use deterministic per-task stratified splits with `seed = 42`.

### Chinese

- dev:
  - `AG 93`
  - `EC 62`
  - `IP 134`
  - `PCC 57`
  - `PLS 35`
  - `Q&A 131`
  - `QG 134`
  - `TMG 134`
  - total `780`
- test:
  - total `7013`

### English

- dev:
  - `AG 104`
  - `EC 130`
  - `IP 130`
  - `PCC 25`
  - `PLS 45`
  - `Q&A 129`
  - `QG 129`
  - `TMG 119`
  - total `811`
- test:
  - total `7291`

Do not change these splits once any reported run has started.

## Required Systems

These system names must exist in the code so experiment bookkeeping stays clean:

- `rule_v2`
- `1b_only`
- `7b_only`
- `cascade_final`
- `cascade_no_calibrator`
- `cascade_no_specialist_prompt`
- `cascade_no_draft_conditioning`

Optional diagnostic system:

- `current_v3`

`current_v3` is optional because the old design is already known to be flawed and is not required to prove the final paper story. If you have enough time, run it on a small Chinese subset for diagnosis only.

## The Experiment Bundle You Must Complete

### E0: Data Sanity Audit

Purpose:

- prove the corrected loader is trustworthy before burning GPU time

No GPU required.

Required outputs:

- one JSON report with per-task counts
- one JSON report with split counts
- one markdown note with five manually checked samples per task family

Success criteria:

- counts exactly match this document
- canonical prompts are sensible
- no stale QG prompt drift into unrelated "成语" prompts

### E1: Calibration Runs On Dev Split

Run on:

- zh dev
- en dev

Systems:

- `1b_only`
- `7b_only`
- `cascade_final`

Purpose:

- choose risk thresholds
- check 1B route quality
- check specialist prompt behavior

Required outputs:

- prediction JSONL
- trace JSONL
- calibration summary JSON

Tune only:

- risk thresholds
- task priors
- simple format-check rules

Do not retune prompts endlessly. Two calibration passes are enough.

### E2: Main Chinese Test

Run on:

- zh test full (`7013`)

Systems:

- `rule_v2`
- `1b_only`
- `7b_only`
- `cascade_final`

Purpose:

- this is the main paper table

Required outputs:

- all raw prediction artifacts
- one overall summary
- one per-task summary
- one route summary

### E3: Main English Supplement

Run on:

- en test full (`7291`)

Systems:

- `1b_only`
- `7b_only`
- `cascade_final`

Purpose:

- show cross-lingual generalization
- this can be a secondary table or appendix table

Do not spend time on `rule_v2` for English unless you finish everything else early.

### E4: Chinese Ablation Study

Run on:

- zh test stratified subset, 25% of each task

Systems:

- `cascade_final`
- `cascade_no_calibrator`
- `cascade_no_specialist_prompt`
- `cascade_no_draft_conditioning`

Purpose:

- support the ablation table without spending full-benchmark GPU time

Why 25% instead of full zh test:

- it is enough for directional evidence
- it is much cheaper
- your main claims already come from E2 and E3

### E5: Routing Analysis Pack

Run on:

- `cascade_final` Chinese full test traces from E2

No new inference required if traces are already saved correctly.

Required analyses:

- accepted-by-1B rate
- 7B invocation rate
- per-task invocation rate
- average latency by task family
- accepted-by-1B accuracy
- escalated-sample accuracy

Purpose:

- this is the core efficiency story of the paper

### E6: Manual Case Study Pack

No new model runs if predictions are already saved.

Create a curated case-study file with:

- 20 successful `1B` direct-accept samples
- 20 successful `7B` refinement samples
- 10 cascade failure samples

For each case include:

- sample id
- task key
- gold answer
- `1B` draft
- final output
- route decision
- short explanation of why the route helped or failed

Purpose:

- support qualitative analysis and failure discussion

## Evaluation Metrics

## Primary Metrics

- `quality_score`
- `format_validity_rate`
- `7b_invocation_rate`
- `latency_avg`
- `latency_p50`
- `latency_p90`

## Routing Metrics

- `accepted_by_1b_rate`
- `accepted_by_1b_quality`
- `escalated_quality`
- `per-task escalation_rate`

## Secondary Metrics

- `tokens_1b_avg`
- `tokens_7b_avg`
- `estimated_cost_proxy`

Use the quality metric hierarchy below.

## Quality Metric Hierarchy

### Tier 1: Deterministic metrics

Use wherever possible:

- exact match for direct short answers
- option match for multiple-choice questions
- structured field presence and schema validity for generated JSON-like tasks
- score extraction checks for grading tasks

These deterministic metrics must always run.

### Tier 2: Cached judge metrics

Use for open-ended tasks where exact match is weak.

Rules:

- run judge only after raw predictions are saved
- cache every judge result under `outputs/eval_cache/`
- never make judge success a dependency for the prediction run itself

Judge targets:

- `QG`
- `TMG`
- `PCC`
- `PLS`
- open-ended `IP`
- open-ended `AG` feedback quality

### Tier 3: Manual audit

Use the case-study pack and a small random audit to validate the judge and route story.

Minimum manual audit size:

- 100 samples total

## Required Artifact Schema

Every saved prediction row must include:

- `sample_id`
- `system_name`
- `task_key`
- `task_family`
- `lang`
- `prediction`
- `ground_truth`
- `route`
- `accepted_by_1b`
- `specialist_name`
- `risk_score`
- `format_valid`
- `latency_seconds`
- `tokens_1b`
- `tokens_7b`

Every saved trace row must include:

- `sample_id`
- `system_name`
- `router_output_raw`
- `router_output_parsed`
- `risk_features`
- `risk_score`
- `risk_threshold`
- `escalated`
- `specialist_name`
- `final_output_raw`
- `validation_report`

## Exact Table Plan For The Paper

Create these tables later from saved outputs. Do not invent new experiment types after the GPU window ends.

### Table 1: Main Chinese Results

Systems:

- `rule_v2`
- `1b_only`
- `7b_only`
- `cascade_final`

Metrics:

- quality
- format validity
- 7B invocation rate
- avg latency

### Table 2: English Supplement

Systems:

- `1b_only`
- `7b_only`
- `cascade_final`

Metrics:

- quality
- format validity
- 7B invocation rate
- avg latency

### Table 3: Routing Efficiency

Use `cascade_final` only.

Break down by:

- task family
- task key
- accepted by 1B vs escalated

### Table 4: Ablation

Systems:

- `cascade_final`
- `cascade_no_calibrator`
- `cascade_no_specialist_prompt`
- `cascade_no_draft_conditioning`

### Table 5: Case Study

Use the manual pack from E6.

## Figure Plan

Generate these figures from saved summaries and traces:

1. final system architecture figure
2. route distribution figure
3. per-task latency bar chart
4. quality-latency Pareto chart
5. accepted-by-1B vs escalated quality chart

## Recommended Command Interface

By the time you run this document, the code should support these commands:

```bash
python main.py --system 1b_only --lang zh --split dev
python main.py --system 7b_only --lang zh --split dev
python main.py --system cascade_final --lang zh --split dev

python main_parallel.py --system rule_v2 --lang zh --split test
python main_parallel.py --system 1b_only --lang zh --split test
python main_parallel.py --system 7b_only --lang zh --split test
python main_parallel.py --system cascade_final --lang zh --split test

python main_parallel.py --system 1b_only --lang en --split test
python main_parallel.py --system 7b_only --lang en --split test
python main_parallel.py --system cascade_final --lang en --split test

python main_parallel.py --system cascade_no_calibrator --lang zh --split ablation
python main_parallel.py --system cascade_no_specialist_prompt --lang zh --split ablation
python main_parallel.py --system cascade_no_draft_conditioning --lang zh --split ablation
```

If your final code uses slightly different command syntax, keep the semantics identical.

## Strict Run Order

Follow this run order exactly:

1. `E0` data sanity audit
2. `E1` calibration runs
3. threshold freeze
4. `E2` Chinese main test
5. `E3` English supplement
6. `E4` ablations
7. `E5` routing analysis
8. `E6` case-study pack

Do not change thresholds after step 3.

## What You Must Not Forget Before GPU Time Ends

Before the hardware window closes, confirm all of the following files exist:

- Chinese main-test predictions for all required systems
- English main-test predictions for all required systems
- Chinese ablation predictions
- all route traces
- all timing summaries
- judge cache for open-ended tasks if available
- manual case-study shortlist with sample ids

If these artifacts exist, the paper can still be written later even if no new inference is possible.

## Final Recommendation

If you are forced to choose what to save, prioritize in this exact order:

1. `cascade_final` full zh test
2. `7b_only` full zh test
3. `1b_only` full zh test
4. `cascade_final` full en test
5. `7b_only` full en test
6. `1b_only` full en test
7. zh ablations
8. `rule_v2` zh test

This ordering protects the paper's main claims even under time pressure.
