import pathlib
import sys
import duckdb
from spec_scorer import SpecQualityScorer

PROJECT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = PROJECT / "specmine.duckdb"

# SPECMINE_DIR can be overridden, otherwise defaults to PROJECT/data/specmine-official
DATA_DIR = PROJECT / "data" / "specmine-official"
JSONL_PATH = DATA_DIR / "specs.jsonl.gz"

if not DB_PATH.exists():
    sys.exit(f"{DB_PATH} not found. Run `python src/build_db.py` first.")

if not JSONL_PATH.exists():
    sys.exit(f"Spec text file not found at {JSONL_PATH}. Please ensure specs.jsonl.gz is in the data folder.")

con = duckdb.connect(str(DB_PATH))
scorer = SpecQualityScorer()

# Register UDF functions for DuckDB
con.create_function("calc_spec_score", lambda text: scorer.evaluate_spec(text)["total_score"], ["VARCHAR"], "DOUBLE")
con.create_function("calc_ac_score", lambda text: scorer.evaluate_spec(text)["ac_score"], ["VARCHAR"], "DOUBLE")
con.create_function("calc_scenario_score", lambda text: scorer.evaluate_spec(text)["scenario_score"], ["VARCHAR"], "DOUBLE")
con.create_function("calc_file_ref_score", lambda text: scorer.evaluate_spec(text)["file_ref_score"], ["VARCHAR"], "DOUBLE")

print("Computing quality scores across specs...")

# Read directly from jsonl.gz file
jsonl_str = JSONL_PATH.as_posix()
con.execute(f"""
CREATE OR REPLACE TABLE spec_quality_scores AS
SELECT 
    file_url_sha16,
    calc_spec_score(content) AS spec_quality_score,
    calc_ac_score(content) AS ac_score,
    calc_scenario_score(content) AS scenario_score,
    calc_file_ref_score(content) AS file_ref_score
FROM read_json_auto('{jsonl_str}')
""")

row_count = con.execute("SELECT COUNT(*) FROM spec_quality_scores").fetchone()[0]
print(f"Successfully computed quality scores for {row_count:,} specifications.")
con.close()