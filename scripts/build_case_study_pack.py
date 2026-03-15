"""
Build the E6 manual case-study pack from saved cascade artifacts.
"""
import argparse
import json
import random
from datetime import datetime
from pathlib import Path

from evaluation.artifact_analysis import (
    diverse_select,
    extract_1b_draft,
    load_joined_rows,
    quality_value,
    route_decision,
    seven_b_invoked,
    write_json,
    write_markdown,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the E6 case-study pack from saved artifacts.")
    parser.add_argument("--predictions", required=True, help="Path to the prediction JSONL file.")
    parser.add_argument("--traces", required=True, help="Path to the trace JSONL file.")
    parser.add_argument("--output-json", help="Optional output path for the case-study JSON.")
    parser.add_argument("--output-md", help="Optional output path for the case-study markdown.")
    parser.add_argument("--extra-audit-count", type=int, default=50, help="Extra random shortlist size for manual audit.")
    return parser.parse_args()


def _default_output(path: Path, suffix: str) -> Path:
    return Path("/opt/pangu/pangu/outputs/results") / f"{path.stem}__case_study_pack{suffix}"


def main() -> None:
    args = _parse_args()
    prediction_path = Path(args.predictions)
    trace_path = Path(args.traces)
    rows = load_joined_rows(prediction_path, trace_path)

    direct_success = sorted(
        [row for row in rows if row.get("accepted_by_1b") is True and _is_success(row)],
        key=_success_sort_key,
    )
    refine_success = sorted(
        [row for row in rows if row.get("accepted_by_1b") is False and seven_b_invoked(row) and _is_success(row)],
        key=_success_sort_key,
    )
    failures = sorted(
        [row for row in rows if _is_failure(row)],
        key=_failure_sort_key,
    )

    direct_cases = [_build_case(row, "1b_direct_success") for row in diverse_select(direct_success, 20)]
    refine_cases = [_build_case(row, "7b_refinement_success") for row in diverse_select(refine_success, 20)]
    failure_cases = [_build_case(row, "cascade_failure") for row in diverse_select(failures, 10)]

    selected_ids = {case["sample_id"] for case in direct_cases + refine_cases + failure_cases}
    extra_pool = [row for row in rows if row["sample_id"] not in selected_ids]
    randomizer = random.Random(42)
    randomizer.shuffle(extra_pool)
    extra_audit = [_build_audit_stub(row) for row in extra_pool[: args.extra_audit_count]]

    report = {
        "generated_at": datetime.now().isoformat(),
        "prediction_file": str(prediction_path),
        "trace_file": str(trace_path),
        "run_name": prediction_path.stem,
        "selected_counts": {
            "1b_direct_success": len(direct_cases),
            "7b_refinement_success": len(refine_cases),
            "cascade_failure": len(failure_cases),
            "extra_manual_audit_shortlist": len(extra_audit),
        },
        "cases": {
            "1b_direct_success": direct_cases,
            "7b_refinement_success": refine_cases,
            "cascade_failure": failure_cases,
        },
        "extra_manual_audit_shortlist": extra_audit,
    }

    json_out = Path(args.output_json) if args.output_json else _default_output(prediction_path, ".json")
    md_out = Path(args.output_md) if args.output_md else _default_output(prediction_path, ".md")
    write_json(json_out, report)
    write_markdown(md_out, _build_markdown(report))

    print(
        json.dumps(
            {
                "case_study_json": str(json_out),
                "case_study_markdown": str(md_out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _is_success(row: dict) -> bool:
    value = quality_value(row)
    return value is not None and value > 0.0 and bool(row.get("format_validity"))


def _is_failure(row: dict) -> bool:
    value = quality_value(row)
    if value is not None:
        return value <= 0.0 or not bool(row.get("format_validity"))
    return not bool(row.get("format_validity"))


def _success_sort_key(row: dict) -> tuple:
    value = quality_value(row)
    return (
        -float(value if value is not None else -1.0),
        row.get("risk_score") or 0.0,
        row.get("sample_id", ""),
    )


def _failure_sort_key(row: dict) -> tuple:
    value = quality_value(row)
    return (
        float(value if value is not None else 1.0),
        0 if not row.get("format_validity") else 1,
        -(row.get("risk_score") or 0.0),
        row.get("sample_id", ""),
    )


def _build_case(row: dict, bucket: str) -> dict:
    trace = row.get("_trace", {}) or {}
    return {
        "sample_id": row.get("sample_id"),
        "task_key": row.get("task_key"),
        "task_family": row.get("task_family"),
        "question": row.get("question", ""),
        "gold_answer": row.get("ground_truth"),
        "one_b_draft": extract_1b_draft(row),
        "final_output": row.get("prediction"),
        "route_decision": route_decision(row),
        "quality_value": quality_value(row),
        "risk_score": row.get("risk_score"),
        "risk_threshold": trace.get("risk_threshold"),
        "specialist_name": row.get("specialist_name") or trace.get("specialist_name", ""),
        "short_explanation": _explain_case(row, trace, bucket),
    }


def _build_audit_stub(row: dict) -> dict:
    return {
        "sample_id": row.get("sample_id"),
        "task_key": row.get("task_key"),
        "route_decision": route_decision(row),
        "quality_value": quality_value(row),
    }


def _explain_case(row: dict, trace: dict, bucket: str) -> str:
    risk_score = row.get("risk_score")
    risk_threshold = trace.get("risk_threshold")
    features = trace.get("risk_features", {}) or {}

    if bucket == "1b_direct_success":
        return (
            f"1B stayed below the frozen threshold ({risk_score} < {risk_threshold}) and the saved output passed the "
            "available offline quality check without invoking 7B."
        )

    if bucket == "7b_refinement_success":
        triggers = []
        if features.get("format_error_flag"):
            triggers.append("the 1B draft failed the format check")
        if features.get("low_confidence_flag"):
            triggers.append("the 1B confidence was low")
        if features.get("length_anomaly_flag"):
            triggers.append("the 1B draft length looked abnormal")
        if not triggers:
            triggers.append("the calibrated risk score crossed the frozen threshold")
        joined = "; ".join(triggers)
        return (
            f"7B refinement was triggered because {joined}. The final saved output then passed the available offline "
            "quality check."
        )

    if not row.get("format_validity"):
        failure_reason = "the final output still failed format validation"
    elif quality_value(row) == 0.0:
        failure_reason = "the final output missed the deterministic target"
    else:
        failure_reason = "the saved artifact remained low quality under the available offline checks"
    return f"The cascade route `{route_decision(row)}` did not recover this sample because {failure_reason}."


def _build_markdown(report: dict) -> str:
    counts = report["selected_counts"]
    return "\n".join(
        [
            "# E6 Case Study Pack",
            "",
            f"- Run name: `{report['run_name']}`",
            f"- 1B direct successes: `{counts['1b_direct_success']}`",
            f"- 7B refinement successes: `{counts['7b_refinement_success']}`",
            f"- Cascade failures: `{counts['cascade_failure']}`",
            f"- Extra manual-audit shortlist: `{counts['extra_manual_audit_shortlist']}`",
            "",
            "The JSON pack contains the full curated cases plus an extra random shortlist so the manual audit can reach 100 samples with the required 20/20/10 structure still preserved.",
        ]
    )


if __name__ == "__main__":
    main()
