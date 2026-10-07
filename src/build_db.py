import os
import pathlib
import subprocess
import sys

import duckdb

SAMPLE_REPO = "https://github.com/shyamagarwal13/specmine-official.git"

# Project root = parent of src/, no matter where the script is run from
PROJECT = pathlib.Path(__file__).resolve().parent.parent

# Default location of the SpecMine sample: <project>/data/specmine-official
# To use a copy stored elsewhere, set the SPECMINE_DIR environment variable.
SAMPLE = pathlib.Path(os.environ.get("SPECMINE_DIR", PROJECT / "data" / "specmine-official"))
DB_PATH = PROJECT / "specmine.duckdb"


def ensure_sample():
    """Clone the SpecMine sample if it is not already on disk."""
    if (SAMPLE / "data").is_dir():
        return
    print(f"SpecMine sample not found at {SAMPLE}. Cloning...")
    try:
        subprocess.run(["git", "clone", SAMPLE_REPO, str(SAMPLE)], check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.exit(
            "Could not clone automatically. Install git, or download the sample from\n"
            f"{SAMPLE_REPO}\ninto {SAMPLE} (or set SPECMINE_DIR to its location)."
        )


def main():
    ensure_sample()
    con = duckdb.connect(str(DB_PATH))

    for pq in sorted((SAMPLE / "data").glob("*.parquet")):
        con.execute(f"""
            CREATE OR REPLACE TABLE {pq.stem} AS
            SELECT * FROM read_parquet('{pq.as_posix()}')
        """)
        n = con.execute(f"SELECT COUNT(*) FROM {pq.stem}").fetchone()[0]
        print(f"{pq.stem}: {n:,} rows")

    jsonl = SAMPLE / "specs.jsonl.gz"
    con.execute(f"""
        CREATE OR REPLACE TABLE spec_text AS
        SELECT * FROM read_json_auto('{jsonl.as_posix()}')
    """)
    print("spec_text:", con.execute("SELECT COUNT(*) FROM spec_text").fetchone()[0], "rows")
    con.close()
    print(f"Database written to {DB_PATH}")


if __name__ == "__main__":
    main()