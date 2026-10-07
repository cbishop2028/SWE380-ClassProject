import duckdb, pathlib

# Location of the cloned SpecMine sample (adjust if you move it)
SAMPLE = pathlib.Path("C:/Users/conno/SWE380/specmine-official")
DATA = SAMPLE / "data"

# Put the database in the project repo, regardless of where the script is run
PROJECT = pathlib.Path(__file__).resolve().parent.parent
con = duckdb.connect(str(PROJECT / "specmine.duckdb"))

for pq in sorted(DATA.glob("*.parquet")):
    con.execute(f"""
        CREATE OR REPLACE TABLE {pq.stem} AS
        SELECT * FROM read_parquet('{pq.as_posix()}')
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {pq.stem}").fetchone()[0]
    print(f"{pq.stem}: {n:,} rows")

con.execute(f"""
    CREATE OR REPLACE TABLE spec_text AS
    SELECT * FROM read_json_auto('{(SAMPLE / "specs.jsonl.gz").as_posix()}')
""")
print("spec_text:", con.execute("SELECT COUNT(*) FROM spec_text").fetchone()[0], "rows")
con.close()