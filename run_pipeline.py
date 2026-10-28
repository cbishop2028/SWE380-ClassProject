"""Portable entry point: python run_pipeline.py --help."""
import argparse
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / "src"))
from build_db import build_database, default_data_dir


def main():
    parser = argparse.ArgumentParser(description="Build and analyze a local SpecMine release")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--db", type=Path, default=PROJECT / "specmine.duckdb")
    parser.add_argument("--output-dir", type=Path, default=PROJECT)
    parser.add_argument("--all-tables", action="store_true")
    parser.add_argument("--include-text", action="store_true")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    build_database(args.data_dir, args.db, args.all_tables, args.include_text)
    command = [sys.executable, str(PROJECT / "src" / "explore.py"),
               "--db", str(args.db.resolve()), "--output-dir", str(args.output_dir.resolve())]
    if args.show:
        command.append("--show")
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
