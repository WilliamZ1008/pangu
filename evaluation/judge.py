"""
Optional post-hoc judge with disk caching.
"""
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Sequence

import requests

from config import GPT5_API_BASE, GPT5_API_KEY, GPT5_MODEL_NAME, OUTPUT_EVAL_CACHE_DIR
from core.prompts import GPT5_JUDGE_PROMPT_ZH


class JudgeRunner:
    """Run the optional GPT judge after predictions are already saved."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = Path(cache_dir or OUTPUT_EVAL_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "Authorization": f"Bearer {GPT5_API_KEY}",
            "Content-Type": "application/json",
        }

    def judge_row(self, row: Dict) -> Dict:
        cache_key = self._cache_key(row)
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        prompt = GPT5_JUDGE_PROMPT_ZH.format(
            task_type=row["task_type"],
            question=row.get("prompt", ""),
            prediction=row["prediction"],
            ground_truth=row["ground_truth"],
        )
        payload = {
            "model": GPT5_MODEL_NAME,
            "messages": [
                {"role": "system", "content": "你是一个严谨的教育专家评估系统。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        try:
            response = requests.post(
                f"{GPT5_API_BASE}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            parsed = json.loads(response.json()["choices"][0]["message"]["content"])
            record = {"request": payload, "response": parsed}
        except Exception as error:
            record = {
                "request": payload,
                "response": {
                    "Error": str(error),
                    "Average": 0,
                    "Reason": "judge request failed",
                },
            }

        cache_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def evaluate_rows(self, rows: Sequence[Dict]) -> list[Dict]:
        evaluated = []
        for row in rows:
            record = self.judge_row(row)
            enriched = dict(row)
            enriched["judge_score"] = record["response"].get("Average")
            enriched["judge_payload"] = record["response"]
            evaluated.append(enriched)
        return evaluated

    def _cache_key(self, row: Dict) -> str:
        payload = {
            "sample_id": row.get("sample_id"),
            "system_name": row.get("system_name", row.get("system")),
            "task_type": row.get("task_type"),
            "prediction": row.get("prediction"),
            "ground_truth": row.get("ground_truth"),
        }
        return hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
