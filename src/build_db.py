"""Import a local SpecMine Parquet release without network access."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb

PROJECT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT / "specmine.duckdb"
REQUIRED = {
    "spec_file_commits": {"file_url_sha16", "repo_name", "seq_from_oldest",
        "commit_sha", "committed_at", "parents", "message", "author_type",
        "committer_type", "author_login", "committer_login", "author_name", "committer_name"},
    "spec_content_features": {"file_url_sha16", "has_acceptance_criteria", "n_words"},
}


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def default_data_dir():
    return Path(os.environ.get("SPECMINE_DIR", PROJECT / "data" / "specmine-official"))


def build_database(data_dir, db_path=DB_PATH, all_tables=False, include_text=False):
    source = Path(data_dir).expanduser().resolve()
    # Accept either the extracted release root or its data/ directory.
    parquet_dir = source / "data" if (source / "data").is_dir() else source
    files = {p.stem: p for p in parquet_dir.glob("*.parquet")}
    missing = set(REQUIRED) - files.keys()
    if missing:
        raise ValueError(f"Missing Parquet tables at {parquet_dir}: {', '.join(sorted(missing))}. "
                         "Extract the dataset first and pass --data-dir pointing to its folder.")
    text = (source if parquet_dir != source else source.parent) / "specs.jsonl.gz"
    if include_text and not text.is_file():
        raise ValueError(f"Specification text not found: {text}")
    # Check schemas before opening or modifying the output database.
    with duckdb.connect() as check:
        for table, required in REQUIRED.items():
            columns = {r[0] for r in check.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(files[table])]).fetchall()}
            if required - columns:
                raise ValueError(f"{table} missing columns: {', '.join(sorted(required - columns))}")
    target = Path(db_path).expanduser().resolve()
    if target in files.values() or target == text:
        raise ValueError("Output database must not replace an input file")
    target.parent.mkdir(parents=True, exist_ok=True)
    selected = files if all_tables else {name: files[name] for name in REQUIRED}
    manifest = {"source_directory": str(source), "built_at_utc": datetime.now(timezone.utc).isoformat(),
                "duckdb_version": duckdb.__version__, "tables": {}}
    with duckdb.connect(str(target)) as con:
        con.execute("BEGIN TRANSACTION")
        try:
            # Clear previously imported tables so a sample/full switch cannot mix releases.
            for (table,) in con.execute("SHOW TABLES").fetchall():
                con.execute(f"DROP TABLE {quote_identifier(table)}")
            for name, path in sorted(selected.items()):
                con.execute(f"CREATE TABLE {quote_identifier(name)} AS SELECT * FROM read_parquet(?)", [str(path)])
                count = con.execute(f"SELECT count(*) FROM {quote_identifier(name)}").fetchone()[0]
                manifest["tables"][name] = {"path": str(path), "bytes": path.stat().st_size,
                                            "modified_ns": path.stat().st_mtime_ns, "rows": count}
                print(f"{name}: {count:,} rows", flush=True)
            if include_text:
                con.execute("CREATE TABLE spec_text AS SELECT * FROM read_json_auto(?)", [str(text)])
            con.execute("CREATE TABLE pipeline_metadata (manifest_json VARCHAR)")
            con.execute("INSERT INTO pipeline_metadata VALUES (?)", [json.dumps(manifest)])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    print(f"Database written to {target}", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--db", type=Path, default=DB_PATH,
                        help="Generated database dedicated to this pipeline; its tables are replaced")
    parser.add_argument("--all-tables", action="store_true")
    parser.add_argument("--include-text", action="store_true")
    args = parser.parse_args()
    try:
        build_database(args.data_dir, args.db, args.all_tables, args.include_text)
    except (ValueError, duckdb.Error, OSError) as exc:
        parser.exit(1, f"Build failed: {exc}\n")


if __name__ == "__main__":
    main()
