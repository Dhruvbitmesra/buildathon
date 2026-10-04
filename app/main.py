"""
Command-line entry point for the SOV pipeline.

    python -m app.main data/input/SOV_H6D2.xlsx
    python -m app.main data/input/SOV_H6D2.xlsx --approve bulk
    python -m app.main data/input/SOV_H6D2.xlsx --decisions decisions.json
    python -m app.main data/input/SOV_H6D2.xlsx --approve all --no-llm

Without an approval option the pipeline stops at the human review gate
and writes output/<file>/review_queue.json. Cleaned_SOV.xlsx is written
only once every recommendation has a decision.
"""

import argparse
import sys
from pathlib import Path

from app.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    # Windows consoles (cp1252) cannot print every character found in
    # client data or LLM text; never crash on output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(description="SOVereign AI pipeline")
    parser.add_argument("file", help="SOV file (.xlsx, .xls or .csv)")
    parser.add_argument(
        "--output",
        default=None,
        help="output directory (default: output/<file name>)",
    )
    parser.add_argument(
        "--approve",
        choices=["none", "bulk", "all"],
        default="none",
        help=(
            "none: stop at review; bulk: approve only bulk-approvable "
            "items; all: approve every item as the named reviewer"
        ),
    )
    parser.add_argument("--reviewer", default="cli-reviewer")
    parser.add_argument("--decisions", help="JSON file of review decisions")
    llm = parser.add_mutually_exclusive_group()
    llm.add_argument("--llm", dest="use_llm", action="store_true", default=None)
    llm.add_argument("--no-llm", dest="use_llm", action="store_false")
    parser.add_argument(
        "--no-memory",
        dest="use_memory",
        action="store_false",
        help="do not use or update the memory of reviewed mappings",
    )
    args = parser.parse_args(argv)

    # Include the extension so sample.csv and sample.xlsx do not
    # overwrite each other's output.
    source = Path(args.file)
    output_dir = args.output or str(
        Path("output") / f"{source.stem}_{source.suffix.lstrip('.')}"
    )

    try:
        result = run_pipeline(
            args.file,
            output_dir=output_dir,
            use_llm=args.use_llm,
            approve=args.approve,
            reviewer=args.reviewer,
            decisions_file=args.decisions,
            use_memory=args.use_memory,
        )
    except Exception as error:  # last-resort guard (NFR-4)
        print(f"ERROR: unexpected failure: {error}")
        return 2

    state = result.state

    print("=" * 64)
    print(f"SOV PIPELINE  {args.file}")
    print("=" * 64)

    if state is not None:
        print(f"Sheet:   {state.selected_sheet} (header row "
              f"{state.header_row + 1 if state.header_row is not None else '-'})")
        mapping = state.metadata.get("schema_mapping_json")

        if mapping:
            mapped = sum(1 for m in mapping["mappings"].values() if m["target"])
            print(f"Mapping: {mapped} mapped, {mapping['unresolved_count']} "
                  f"unresolved, overall confidence {mapping['overall_confidence']}")

        if state.quality_report is not None:
            report = state.quality_report
            print(f"Quality: {report.total_issues} issues, intake score "
                  f"{report.intake_quality_score}")

        if state.review_ledger is not None:
            print(f"Review:  {state.review_ledger.summary()}")

        for warning in state.warnings:
            print(f"WARNING: {warning}")

    for stage, seconds in result.timings.items():
        print(f"  {stage:<16} {seconds:6.1f}s")

    for name, path in result.artifacts.items():
        print(f"  -> {name}: {path}")

    for error in result.errors:
        print(f"{'NOTE' if result.ok else 'ERROR'}: {error}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
