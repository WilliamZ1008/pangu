"""
Single-process offline experiment entrypoint.
"""
import argparse
import json

from experiment_runner import ExperimentRunner
from inference_engine import SUPPORTED_SYSTEMS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single offline EduBench experiment.")
    parser.add_argument("--system", required=True, choices=SUPPORTED_SYSTEMS, help="Experiment system name.")
    parser.add_argument("--lang", required=True, choices=["zh", "en", "all"], help="Benchmark language.")
    parser.add_argument(
        "--split",
        required=True,
        choices=["all", "dev", "test", "ablation"],
        help="Deterministic split name.",
    )
    parser.add_argument("--do-judge", action="store_true", help="Run the optional GPT judge after predictions.")
    parser.add_argument("--sample-limit", type=int, help="Optional hard cap for debugging a run.")
    parser.add_argument(
        "--sample-fraction",
        type=float,
        help="Optional deterministic stratified fraction to keep per task for faster pilot runs.",
    )
    parser.add_argument("--output-tag", default="", help="Optional tag inserted into artifact filenames.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    runner = ExperimentRunner()
    result = runner.run(
        system_name=args.system,
        lang=args.lang,
        split=args.split,
        do_judge=args.do_judge,
        sample_limit=args.sample_limit,
        sample_fraction=args.sample_fraction,
        max_workers=1,
        output_tag=args.output_tag,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
