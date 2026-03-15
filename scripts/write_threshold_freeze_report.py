"""
Write a threshold freeze report from the completed E1 calibration artifacts.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from core.risk_calibrator import RiskCalibrator
from evaluation.artifact_analysis import read_json, write_json, write_markdown


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the operational threshold freeze report for the paper run.")
    parser.add_argument("--e1-summary", required=True, help="Path to the aggregate E1 calibration summary JSON.")
    parser.add_argument("--decision", default="freeze", choices=["freeze", "hold"], help="Operational freeze decision.")
    parser.add_argument("--output-json", help="Optional output path for the JSON report.")
    parser.add_argument("--output-md", help="Optional output path for the markdown note.")
    return parser.parse_args()


def _default_path(root: Path, suffix: str) -> Path:
    return root / f"threshold_freeze_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}"


def main() -> None:
    args = _parse_args()
    e1_summary_path = Path(args.e1_summary)
    e1_summary = read_json(e1_summary_path)
    results_dir = Path("/opt/pangu/pangu/outputs/results")
    json_path = Path(args.output_json) if args.output_json else _default_path(results_dir, ".json")
    md_path = Path(args.output_md) if args.output_md else _default_path(results_dir, ".md")

    calibrator = RiskCalibrator()
    threshold_review = e1_summary.get("threshold_review", {})
    report = {
        "generated_at": datetime.now().isoformat(),
        "decision": args.decision,
        "decision_type": "operational_threshold_freeze",
        "e1_summary_file": str(e1_summary_path),
        "e1_run_tag": e1_summary.get("run_tag", ""),
        "e1_summary_recommendation": threshold_review.get("recommendation", "unknown"),
        "e1_summary_reasons": threshold_review.get("reasons", []),
        "current_family_thresholds": dict(calibrator.THRESHOLDS),
        "current_task_key_thresholds": dict(calibrator.TASK_KEY_THRESHOLDS),
        "review_signals": threshold_review.get("signals", []),
        "notes": [
            "The live E1 rerun artifacts remain the formal basis for calibration review.",
            "The current code snapshot includes task-key thresholds for Q&A and EC that were applied after the saved E1 rerun completed.",
            "Thresholds are frozen operationally for the paper run so E2-E6 artifacts can be captured without more calibration churn.",
            "Do not change thresholds again until the full paper-stage artifact bundle is saved.",
        ],
    }
    write_json(json_path, report)

    markdown = "\n".join(
        [
            "# Threshold Freeze Report",
            "",
            f"- Generated at: `{report['generated_at']}`",
            f"- E1 summary: `{report['e1_summary_file']}`",
            f"- E1 aggregate recommendation: `{report['e1_summary_recommendation']}`",
            f"- Operational decision: `{report['decision']}`",
            "",
            "## Current Threshold Snapshot",
            "",
            f"- Family thresholds: `{report['current_family_thresholds']}`",
            f"- Task-key thresholds: `{report['current_task_key_thresholds']}`",
            "",
            "## Decision Notes",
            "",
            *[f"- {note}" for note in report["notes"]],
            "",
            "## E1 Review Reasons",
            "",
            *[f"- {reason}" for reason in report["e1_summary_reasons"]],
        ]
    )
    write_markdown(md_path, markdown)

    print(
        json.dumps(
            {
                "json_report": str(json_path),
                "markdown_report": str(md_path),
                "decision": report["decision"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
