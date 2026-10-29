import os
import pathlib
import subprocess
import sys

import duckdb

SAMPLE_REPO = "https://github.com/shyamagarwal13/specmine-official.git"

# Project root = parent of src/, no matter where the script is run from
PROJECT = pathlib.Path(__file__).resolve().parent.parent

# Default: the 500-repo sample in <project>/data/specmine-official
# For the full dataset, set SPECMINE_DIR to the folder that contains data\
SAMPLE = pathlib.Path(os.environ.get("SPECMINE_DIR", PROJECT / "data" / "specmine-official"))
DB_PATH = PROJECT / "specmine.duckdb"


def ensure_sample():
    """Clone the SpecMine sample if it is not already on disk."""
    if (SAMPLE / "data").is_dir():
        return
    print(f"SpecMine data not found at {SAMPLE}. Cloning the sample...")
    try:
        subprocess.run(["git", "clone", SAMPLE_REPO, str(SAMPLE)], check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.exit(
            "Could not clone automatically. Install git, or download the sample from\n"
            f"{SAMPLE_REPO}\ninto {SAMPLE} (or set SPECMINE_DIR to its location)."
        )


def main():
    ensure_sample()
    print(f"Using data from {SAMPLE}")
    con = duckdb.connect(str(DB_PATH))
    data = SAMPLE / "data"

    # Views read the Parquet files directly instead of copying them,
    # so the database file stays small even with the full dataset.
    for pq in sorted(data.glob("*.parquet")):
        con.execute(f"""
            CREATE OR REPLACE VIEW {pq.stem} AS
            SELECT * FROM read_parquet('{pq.as_posix()}')
        """)
        n = con.execute(f"SELECT COUNT(*) FROM {pq.stem}").fetchone()[0]
        print(f"{pq.stem}: {n:,} rows")

    # Spec text is optional (not needed for the acceptance-criteria analysis)
    jsonl = SAMPLE / "specs.jsonl.gz"
    if jsonl.exists():
        con.execute(f"""
            CREATE OR REPLACE VIEW spec_text AS
            SELECT * FROM read_json_auto('{jsonl.as_posix()}')
        """)
        print("spec_text: loaded")
    else:
        print("spec_text: skipped (specs.jsonl.gz not found)")

    con.close()
    print(f"Database written to {DB_PATH}")


if __name__ == "__main__":
    main()
