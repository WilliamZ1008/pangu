"""
Artifact storage for predictions, traces, and summaries.
"""
import json
from pathlib import Path
from typing import Dict, Sequence

from config import LEGACY_OUTPUT_RESULTS_DIR, OUTPUT_PREDICTION_DIR, OUTPUT_SUMMARY_DIR, OUTPUT_TRACE_DIR


class ResultStore:
    """Persist artifacts with consistent paths and filenames."""

    def __init__(self):
        self.prediction_dir = Path(OUTPUT_PREDICTION_DIR)
        self.trace_dir = Path(OUTPUT_TRACE_DIR)
        self.summary_dir = Path(OUTPUT_SUMMARY_DIR)
        self.result_dir = Path(LEGACY_OUTPUT_RESULTS_DIR)
        for path in (self.prediction_dir, self.trace_dir, self.summary_dir, self.result_dir):
            path.mkdir(parents=True, exist_ok=True)

    def save_predictions(self, run_name: str, rows: Sequence[Dict]) -> str:
        path = self.prediction_dir / f"{run_name}.jsonl"
        self._write_jsonl(path, rows)
        return str(path)

    def save_traces(self, run_name: str, traces: Sequence[Dict]) -> str:
        path = self.trace_dir / f"{run_name}.jsonl"
        self._write_jsonl(path, traces)
        return str(path)

    def save_summary(self, run_name: str, summary: Dict) -> str:
        path = self.summary_dir / f"{run_name}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
        return str(path)

    def save_per_task_summary(self, run_name: str, payload: Dict) -> str:
        path = self.result_dir / f"{run_name}__per_task.json"
        self._write_json(path, payload)
        return str(path)

    def save_per_route_summary(self, run_name: str, payload: Dict) -> str:
        path = self.result_dir / f"{run_name}__per_route.json"
        self._write_json(path, payload)
        return str(path)

    def save_report(self, filename: str, payload: Dict) -> str:
        path = self.result_dir / filename
        self._write_json(path, payload)
        return str(path)

    def _write_jsonl(self, path: Path, rows: Sequence[Dict]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _write_json(self, path: Path, payload: Dict) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
