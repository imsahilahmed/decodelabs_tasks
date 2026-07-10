"""
run.py
------
"The Entry Point: CLI Configuration with Argparse" (slide 14) and
"Structuring the Enterprise Generation Framework" (slide 5).

Two modes:
  1. Single mode  : python run.py --product "..." --platform linkedin --tone witty --description "..."
  2. Batch mode   : python run.py --batch jobs.csv
     CSV columns expected: product_name,platform,tone,description[,temperature,top_p]

Run `python run.py --help` for full usage.
"""

from __future__ import annotations
import argparse
import asyncio
import csv
import json
import sys

from inference_client import generate_copy_sync
from pipeline import CopyJob, run_batch
from prompt_compiler import compile_prompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automated Copywriting & Tone Transformer — DecodeLabs Project 2"
    )
    parser.add_argument("--product", type=str, help="Product name, e.g. 'AquaFlow Bottle'")
    parser.add_argument(
        "--platform",
        type=str,
        choices=["linkedin", "instagram", "email", "twitter"],
        help="Target platform",
    )
    parser.add_argument("--tone", type=str, help="Desired tone, e.g. 'witty', 'professional'")
    parser.add_argument("--description", type=str, help="Raw product description / facts")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Creativity control (0.2 = consistent/factual, 0.8 = diverse/witty). Default 0.7.",
    )
    parser.add_argument(
        "--top-p", dest="top_p", type=float, default=0.95, help="Nucleus sampling cutoff. Default 0.95."
    )
    parser.add_argument(
        "--batch",
        type=str,
        metavar="CSV_PATH",
        help="Path to a CSV file of jobs for concurrent bulk generation",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Optional path to write JSON results to (batch mode)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the compiled prompt instead of calling the model",
    )
    return parser


def run_single(args: argparse.Namespace) -> None:
    if not all([args.product, args.platform, args.tone, args.description]):
        print(
            "Single mode requires --product, --platform, --tone, and --description.\n"
            "(Or use --batch <csv_path> for bulk jobs.)",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.dry_run:
        prompt = compile_prompt(args.product, args.platform, args.tone, args.description)
        print(prompt)
        return

    result = generate_copy_sync(
        compile_prompt(args.product, args.platform, args.tone, args.description),
        temperature=args.temperature,
        top_p=args.top_p,
    )
    print(json.dumps(result.model_dump(), indent=2))


def load_jobs_from_csv(path: str) -> list[CopyJob]:
    jobs: list[CopyJob] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            jobs.append(
                CopyJob(
                    product_name=row["product_name"],
                    platform=row["platform"],
                    tone=row["tone"],
                    product_description=row["description"],
                    temperature=float(row.get("temperature") or 0.7),
                    top_p=float(row.get("top_p") or 0.95),
                )
            )
    return jobs


def run_batch_mode(args: argparse.Namespace) -> None:
    jobs = load_jobs_from_csv(args.batch)
    print(f"Loaded {len(jobs)} jobs from {args.batch}. Running concurrently...")
    results = asyncio.run(run_batch(jobs))
    payload = [r.model_dump() for r in results]

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Wrote {len(payload)} results to {args.out}")
    else:
        print(json.dumps(payload, indent=2))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.batch:
        run_batch_mode(args)
    else:
        run_single(args)


if __name__ == "__main__":
    main()
