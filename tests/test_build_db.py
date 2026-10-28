import json
from pathlib import Path
import sys
import tempfile
import unittest

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from build_db import build_database, REQUIRED


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "someone's dataset"
        self.data = self.root / "data"
        self.data.mkdir(parents=True)
        self.db = Path(self.tmp.name) / "output" / "test.duckdb"
        with duckdb.connect() as con:
            for table, columns in REQUIRED.items():
                select = ", ".join(f"'value' AS {column}" for column in sorted(columns))
                con.execute(f"COPY (SELECT {select}) TO ? (FORMAT PARQUET)",
                            [str(self.data / (table + ".parquet"))])
            con.execute("COPY (SELECT 1 AS x) TO ? (FORMAT PARQUET)",
                        [str(self.data / "extra.parquet")])

    def tearDown(self):
        self.tmp.cleanup()

    def test_root_path_metadata_and_only_required_tables(self):
        build_database(self.root, self.db)
        with duckdb.connect(str(self.db)) as con:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            self.assertEqual(tables, set(REQUIRED) | {"pipeline_metadata"})
            metadata = json.loads(con.execute("SELECT manifest_json FROM pipeline_metadata").fetchone()[0])
            self.assertEqual(metadata["source_directory"], str(self.root.resolve()))
            self.assertEqual(metadata["tables"]["spec_file_commits"]["rows"], 1)

    def test_direct_data_path_and_rebuild_removes_stale_tables(self):
        build_database(self.data, self.db, all_tables=True)
        build_database(self.data, self.db)
        with duckdb.connect(str(self.db)) as con:
            self.assertNotIn("extra", {r[0] for r in con.execute("SHOW TABLES").fetchall()})

    def test_invalid_source_preserves_existing_database(self):
        build_database(self.root, self.db)
        (self.data / "spec_file_commits.parquet").unlink()
        with self.assertRaisesRegex(ValueError, "Missing Parquet"):
            build_database(self.root, self.db)
        with duckdb.connect(str(self.db)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM spec_file_commits").fetchone()[0], 1)

    def test_missing_column_rejected_before_build(self):
        with duckdb.connect() as con:
            con.execute("COPY (SELECT 1 AS wrong) TO ? (FORMAT PARQUET)",
                        [str(self.data / "spec_file_commits.parquet")])
        with self.assertRaisesRegex(ValueError, "missing columns"):
            build_database(self.root, self.db)
        self.assertFalse(self.db.exists())

    def test_text_is_optional_but_explicit_request_is_checked(self):
        with self.assertRaisesRegex(ValueError, "text not found"):
            build_database(self.root, self.db, include_text=True)
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
