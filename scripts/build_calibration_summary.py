#!/usr/bin/env python3
"""
CLI helper for building the aggregate E1 calibration summary JSON.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import OUTPUT_SUMMARY_DIR
from evaluation.calibration_summary import CalibrationSummaryBuilder


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate E1 per-run summaries into one calibration summary JSON.")
    parser.add_argument("--run-tag", required=True, help="Shared output tag used by the E1 suite.")
    parser.add_argument("--output", help="Optional output path. Defaults to outputs/summaries/<run-tag>.json.")
    parser.add_argument("--summary-dir", help="Optional directory containing per-run summary JSON files.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    builder = CalibrationSummaryBuilder(summary_dir=Path(args.summary_dir) if args.summary_dir else None)
    output_path = Path(args.output) if args.output else Path(OUTPUT_SUMMARY_DIR) / f"{args.run_tag}.json"
    saved_path = builder.save(args.run_tag, output_path=output_path)
    payload = json.loads(saved_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "summary_file": str(saved_path),
                "complete": payload.get("complete"),
                "threshold_recommendation": payload.get("threshold_review", {}).get("recommendation"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
