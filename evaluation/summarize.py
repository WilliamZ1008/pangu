"""
Summary builder for offline experiment artifacts.
"""
from collections import defaultdict
from datetime import datetime
from typing import Dict, Sequence

from evaluation.metrics import MetricSuite


class SummaryBuilder:
    """Build overall, per-task, and per-route summaries."""

    def __init__(self, metric_suite: MetricSuite | None = None):
        self.metric_suite = metric_suite or MetricSuite()

    def build(self, scored_rows: Sequence[Dict], *, system_name: str, lang: str, split: str, warnings: Sequence[str] | None = None) -> Dict:
        per_task = defaultdict(list)
        per_route = defaultdict(list)
        for row in scored_rows:
            per_task[row["task_key"]].append(row)
            per_route[row["route"]].append(row)

        return {
            "system_name": system_name,
            "lang": lang,
            "split": split,
            "generated_at": datetime.now().isoformat(),
            "warnings": list(warnings or []),
            "overall_summary": self.metric_suite.aggregate(scored_rows),
            "per_task_summary": {
                task_key: self.metric_suite.aggregate(rows)
                for task_key, rows in per_task.items()
            },
            "per_route_summary": {
                route: self.metric_suite.aggregate(rows)
                for route, rows in per_route.items()
            },
        }
