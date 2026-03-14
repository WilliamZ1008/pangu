"""
Backward-compatible wrapper around the new evaluation package.
"""
import argparse
import json
from pathlib import Path
from typing import Dict, List, Sequence

from evaluation.judge import JudgeRunner
from evaluation.summarize import SummaryBuilder


GPT5Judge = JudgeRunner


def evaluate_prediction_rows(prediction_rows: Sequence[Dict], cache_dir: Path | None = None) -> List[Dict]:
    return JudgeRunner(cache_dir=cache_dir).evaluate_rows(prediction_rows)


def recompute_from_prediction_file(
    prediction_file: Path,
    do_judge: bool = False,
    summary_out: Path | None = None,
) -> Dict:
    rows = _read_jsonl(prediction_file)
    if do_judge:
        rows = JudgeRunner().evaluate_rows(rows)

    warnings = []
    if not do_judge:
        warnings.append(
            "Summary recomputed without judge scores. This is suitable for offline analysis, not final paper tables."
        )

    if rows:
        system_name = rows[0].get("system_name", "")
        lang = rows[0].get("lang", "")
        split = rows[0].get("split", "")
    else:
        system_name = ""
        lang = ""
        split = ""

    summary = SummaryBuilder().build(
        rows,
        system_name=system_name,
        lang=lang,
        split=split,
        warnings=warnings,
    )
    if summary_out is not None:
        summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _read_jsonl(path: Path) -> List[Dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute offline experiment summaries from saved predictions.")
    parser.add_argument("--predictions", required=True, help="Path to the prediction JSONL file.")
    parser.add_argument("--summary-out", help="Optional path for the recomputed summary JSON.")
    parser.add_argument("--do-judge", action="store_true", help="Run the optional cached judge.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = recompute_from_prediction_file(
        prediction_file=Path(args.predictions),
        do_judge=args.do_judge,
        summary_out=Path(args.summary_out) if args.summary_out else None,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
