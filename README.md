# Pangu Offline Research Workspace

`/opt/pangu/pangu` is now organized around a paper-first offline experiment pipeline built on EduBench, not around chat-serving.

## Final system direction

The main implementation target is a prompt-specialized `1B -> 7B` adaptive cascade:

1. normalize one EduBench sample
2. ask `1B` for a structured router output
3. compute calibrated risk
4. accept the `1B` draft on low risk
5. escalate to one prompt-specialized `7B` role on high risk
6. validate and save the final prediction and full route trace

Supported experiment systems:

- `rule_v2`
- `current_v3`
- `1b_only`
- `7b_only`
- `cascade_final`
- `cascade_no_calibrator`
- `cascade_no_specialist_prompt`
- `cascade_no_draft_conditioning`

## Important directories

```text
/opt/pangu/pangu
├── core/
│   ├── schemas.py
│   ├── request_normalizer.py
│   ├── expert_router.py
│   ├── risk_calibrator.py
│   ├── route_trace.py
│   ├── prompts.py
│   └── prompting/
├── services/
│   ├── model_clients.py
│   ├── output_parser.py
│   └── result_store.py
├── evaluation/
│   ├── metrics.py
│   ├── judge.py
│   └── summarize.py
├── outputs/
│   ├── predictions/
│   ├── traces/
│   ├── summaries/
│   └── eval_cache/
├── config.py
├── data_loader.py
├── inference_engine.py
├── experiment_runner.py
├── main.py
├── main_parallel.py
└── evaluator.py
```

## Core workflow

- `data_loader.py`: canonical shared-8 loading with stable sample IDs and deterministic splits
- `split=ablation`: deterministic 25% stratified subset of the test split for low-cost ablations
- `core/request_normalizer.py`: final normalized sample schema
- `core/prompting/`: all final router/specialist/repair prompts
- `services/model_clients.py`: all vLLM HTTP calls
- `services/output_parser.py`: router parsing and output validation
- `inference_engine.py`: orchestration only
- `experiment_runner.py`: shared batch runner for serial and parallel runs
- `evaluation/`: deterministic metrics, summaries, and optional judge cache

## Running the system

Start one `1B` service:

```bash
cd /opt/pangu/pangu
bash scripts/run_service_1b.sh
```

Start one stable `7B` service:

```bash
cd /opt/pangu/pangu
bash scripts/run_service_7b.sh
```

Run one experiment:

```bash
cd /opt/pangu/pangu
python main.py --system cascade_final --lang zh --split test
```

Run one parallel experiment:

```bash
cd /opt/pangu/pangu
python main_parallel.py --system cascade_final --lang zh --split test --max-workers 4
```

Convenience wrappers:

```bash
bash scripts/run_calibration.sh
bash scripts/run_eval.sh
bash scripts/run_eval_parallel.sh
```

## Output artifacts

Every run writes:

- one prediction JSONL
- one route trace JSONL
- one summary JSON
- one calibration summary JSON when `scripts/run_calibration.sh --output-tag <tag>` is used
- optional judge cache entries when `--do-judge` is used

If `--do-judge` is omitted, summaries are explicitly marked as diagnostic-only.

## Post-hoc evaluation

Predictions can be rescored without rerunning GPUs:

```bash
cd /opt/pangu/pangu
python evaluator.py --predictions outputs/predictions/<run>.jsonl
python evaluator.py --predictions outputs/predictions/<run>.jsonl --do-judge
```

## API/frontend status

The API/frontend path is still secondary:

- `core/agent.py` is incomplete
- `api/routes/chat.py` depends on missing serving glue
- `frontend/` should not block offline experiments

The intended order is still: stabilize offline benchmark first, then return to demo surfaces.
