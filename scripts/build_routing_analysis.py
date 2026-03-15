"""
Build the E5 routing analysis pack from saved cascade artifacts.
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from evaluation.artifact_analysis import (
    load_joined_rows,
    mean_or_none,
    quality_value,
    read_json,
    route_decision,
    seven_b_invoked,
    write_json,
    write_markdown,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an E5 routing analysis report from saved artifacts.")
    parser.add_argument("--predictions", required=True, help="Path to the prediction JSONL file.")
    parser.add_argument("--traces", required=True, help="Path to the trace JSONL file.")
    parser.add_argument("--summary", help="Optional path to the saved summary JSON.")
    parser.add_argument("--output-json", help="Optional output path for the routing analysis JSON.")
    parser.add_argument("--output-md", help="Optional output path for the routing analysis markdown.")
    return parser.parse_args()


def _default_output(path: Path, suffix: str) -> Path:
    return Path("/opt/pangu/pangu/outputs/results") / f"{path.stem}__routing_analysis{suffix}"


def main() -> None:
    args = _parse_args()
    prediction_path = Path(args.predictions)
    trace_path = Path(args.traces)
    summary_path = Path(args.summary) if args.summary else None

    rows = load_joined_rows(prediction_path, trace_path)
    summary = read_json(summary_path) if summary_path else {}
    overall_summary = summary.get("overall_summary", {})

    accepted_rows = [row for row in rows if row.get("accepted_by_1b") is True]
    escalated_rows = [row for row in rows if row.get("accepted_by_1b") is False or seven_b_invoked(row)]
    invoked_rows = [row for row in rows if seven_b_invoked(row)]

    per_task: dict[str, list[dict]] = defaultdict(list)
    per_family: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        per_task[str(row.get("task_key", ""))].append(row)
        per_family[str(row.get("task_family", ""))].append(row)

    per_task_invocation = {}
    for task_key, task_rows in sorted(per_task.items()):
        per_task_invocation[task_key] = {
            "total_items": len(task_rows),
            "7b_invocation_rate": len([row for row in task_rows if seven_b_invoked(row)]) / len(task_rows),
            "accepted_by_1b_rate": len([row for row in task_rows if row.get("accepted_by_1b") is True]) / len(task_rows),
            "quality_score": mean_or_none(quality_value(row) for row in task_rows),
        }

    latency_by_family = {}
    for task_family, family_rows in sorted(per_family.items()):
        latency_by_family[task_family] = {
            "total_items": len(family_rows),
            "latency_avg": mean_or_none(float(row.get("latency_seconds", 0.0)) for row in family_rows),
        }

    report = {
        "generated_at": datetime.now().isoformat(),
        "prediction_file": str(prediction_path),
        "trace_file": str(trace_path),
        "summary_file": str(summary_path) if summary_path else "",
        "run_name": prediction_path.stem,
        "system_name": rows[0].get("system_name", "") if rows else "",
        "lang": rows[0].get("lang", "") if rows else "",
        "split": rows[0].get("split", "") if rows else "",
        "overall": {
            "total_items": len(rows),
            "accepted_by_1b_rate": overall_summary.get("accepted_by_1b_rate"),
            "7b_invocation_rate": overall_summary.get("7b_invocation_rate"),
            "accepted_by_1b_accuracy": mean_or_none(quality_value(row) for row in accepted_rows),
            "escalated_sample_accuracy": mean_or_none(quality_value(row) for row in escalated_rows),
            "accepted_by_1b_count": len(accepted_rows),
            "7b_invocation_count": len(invoked_rows),
            "route_counts": _route_counts(rows),
        },
        "per_task_invocation_rate": per_task_invocation,
        "latency_by_task_family": latency_by_family,
    }

    json_out = Path(args.output_json) if args.output_json else _default_output(prediction_path, ".json")
    md_out = Path(args.output_md) if args.output_md else _default_output(prediction_path, ".md")
    write_json(json_out, report)
    write_markdown(md_out, _build_markdown(report))

    print(
        json.dumps(
            {
                "routing_analysis_json": str(json_out),
                "routing_analysis_markdown": str(md_out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _route_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[route_decision(row)] += 1
    return dict(sorted(counts.items()))


def _build_markdown(report: dict) -> str:
    overall = report["overall"]
    lines = [
        "# E5 Routing Analysis",
        "",
        f"- Run name: `{report['run_name']}`",
        f"- System: `{report['system_name']}`",
        f"- Lang/split: `{report['lang']} / {report['split']}`",
        f"- Total items: `{overall['total_items']}`",
        f"- accepted_by_1b_rate: `{overall['accepted_by_1b_rate']}`",
        f"- 7b_invocation_rate: `{overall['7b_invocation_rate']}`",
        f"- accepted_by_1b_accuracy: `{overall['accepted_by_1b_accuracy']}`",
        f"- escalated_sample_accuracy: `{overall['escalated_sample_accuracy']}`",
        "",
        "## Per-task Invocation Rate",
        "",
        "| task_key | total_items | 7b_invocation_rate | accepted_by_1b_rate | quality_score |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for task_key, payload in report["per_task_invocation_rate"].items():
        lines.append(
            f"| {task_key} | {payload['total_items']} | {payload['7b_invocation_rate']:.4f} | "
            f"{payload['accepted_by_1b_rate']:.4f} | {payload['quality_score']} |"
        )

    lines.extend(
        [
            "",
            "## Average Latency By Task Family",
            "",
            "| task_family | total_items | latency_avg |",
            "| --- | ---: | ---: |",
        ]
    )
    for task_family, payload in report["latency_by_task_family"].items():
        lines.append(f"| {task_family} | {payload['total_items']} | {payload['latency_avg']:.4f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
