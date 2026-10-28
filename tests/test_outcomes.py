import sys
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from outcomes import create_outcome_views


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute('''CREATE TABLE spec_file_commits (
            file_url_sha16 VARCHAR, seq_from_oldest INTEGER, commit_sha VARCHAR,
            committed_at VARCHAR, parents VARCHAR, message VARCHAR,
            author_type VARCHAR, committer_type VARCHAR, author_login VARCHAR,
            committer_login VARCHAR, author_name VARCHAR, committer_name VARCHAR)''')
        self.con.execute("CREATE TABLE spec_content_features AS SELECT 's' AS file_url_sha16")
        self.add(1, '2026-01-01T00:00:00Z')

    def tearDown(self):
        self.con.close()

    def add(self, seq, time, parents='a' * 40, message='fix bug',
            author_type='User', committer_type='User', login='person', sha=None):
        self.con.execute('INSERT INTO spec_file_commits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         ['s', seq, sha or str(seq), time, parents, message,
                          author_type, committer_type, login, 'person', 'Person', 'Person'])

    def counts(self):
        create_outcome_views(self.con)
        return self.con.execute('SELECT n_later_commits, n_fixlike_later FROM spec_outcomes').fetchone()

    def test_window_boundaries_and_timezone(self):
        self.add(2, '2026-01-01T00:00:00Z')
        self.add(3, '2026-01-31T00:00:00Z')
        self.add(4, '2026-01-31T00:00:01Z')
        self.add(5, '2026-01-01T01:00:01+01:00')
        self.add(6, '2025-12-31T23:59:59Z')
        self.assertEqual(self.counts(), (2, 2))

    def test_bots_on_either_identity_and_login(self):
        self.add(2, '2026-01-02T00:00:00Z', author_type='Bot')
        self.add(3, '2026-01-02T00:00:00Z', committer_type='Bot')
        self.add(4, '2026-01-02T00:00:00Z', login='dependabot[bot]')
        self.add(5, '2026-01-02T00:00:00Z', login='robotics-person')
        self.assertEqual(self.counts(), (1, 1))

    def test_parent_metadata_and_not_message_detect_merge(self):
        self.add(2, '2026-01-02T00:00:00Z', parents='a'*40 + ', ' + 'b'*40)
        self.add(3, '2026-01-02T00:00:00Z', parents=None)
        self.add(4, '2026-01-02T00:00:00Z', parents='invalid')
        self.add(5, '2026-01-02T00:00:00Z', message='Merge documentation terminology')
        self.assertEqual(self.counts(), (1, 0))

    def test_duplicate_sha_and_keyword_boundaries(self):
        self.add(2, '2026-01-02T00:00:00Z', sha='duplicate')
        self.add(2, '2026-01-02T00:00:00Z', sha='duplicate')
        self.add(3, '2026-01-02T00:00:00Z', message='add prefix and debug logging')
        self.add(4, None)
        self.assertEqual(self.counts(), (2, 1))

    def test_bot_baseline_does_not_shift_window(self):
        self.con.execute("UPDATE spec_file_commits SET author_type='Bot'")
        self.add(2, '2026-01-30T00:00:00Z')
        self.add(3, '2026-02-02T00:00:00Z')
        self.assertEqual(self.counts(), (1, 1))

    def test_invalid_baseline_is_flagged(self):
        self.con.execute("UPDATE spec_file_commits SET committed_at='invalid'")
        self.add(2, '2026-01-02T00:00:00Z')
        self.assertEqual(self.counts(), (0, 0))
        self.assertFalse(self.con.execute('SELECT has_valid_baseline FROM spec_outcomes').fetchone()[0])


if __name__ == '__main__':
    unittest.main()

