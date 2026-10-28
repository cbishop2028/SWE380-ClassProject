import sys
from pathlib import Path
import unittest

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from comparisons import create_comparison_data, comparison_tables


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("SET TimeZone='UTC'")
        self.con.execute("""CREATE TABLE commit_audit (
            file_url_sha16 VARCHAR, repo_name VARCHAR, commit_sha VARCHAR,
            commit_time TIMESTAMPTZ, baseline_time TIMESTAMPTZ,
            is_bot BOOLEAN, parents_known BOOLEAN, is_merge BOOLEAN)""")
        self.con.execute("""CREATE TABLE spec_outcomes (
            file_url_sha16 VARCHAR, baseline_time TIMESTAMPTZ, has_valid_baseline BOOLEAN,
            has_acceptance_criteria INTEGER, n_words INTEGER, n_fixlike_later INTEGER)""")

    def tearDown(self):
        self.con.close()

    def spec(self, name, repo, group, words, fixed, baseline='2026-02-01T00:00:00Z'):
        self.con.execute('INSERT INTO spec_outcomes VALUES (?, ?, true, ?, ?, ?)',
                         [name, baseline, group, words, fixed])
        self.event(name,repo,name,baseline,baseline)

    def event(self, name, repo, sha, time, baseline='2026-02-01T00:00:00Z', bot=False, merge=False):
        self.con.execute('INSERT INTO commit_audit VALUES (?,?,?,?,?,?,true,?)',
                         [name,repo,sha,time,baseline,bot,merge])

    def test_activity_window_deduplication_and_exclusions(self):
        self.spec('a','repo',0,200,0)
        self.event('a','repo','start','2026-01-02T00:00:00Z')
        self.event('b','repo','start','2026-01-02T00:00:00Z')
        self.event('a','repo','old','2026-01-01T23:59:59Z')
        self.event('a','repo','bot','2026-01-15T00:00:00Z',bot=True)
        self.event('a','repo','merge','2026-01-15T00:00:00Z',merge=True)
        self.event('a','repo','future','2026-02-02T00:00:00Z')
        create_comparison_data(self.con)
        self.assertEqual(self.con.execute('SELECT prior_30d_observed_commits FROM comparison_specs').fetchone()[0],1)

    def test_length_boundaries_and_zero_prior_activity(self):
        for i, words in enumerate([0,249,250,499,500,999,1000,1999,2000,None,-1]):
            self.spec(str(i),str(i),i%2,words,0)
        create_comparison_data(self.con)
        counts = dict(self.con.execute('SELECT length_band,count(*) FROM comparison_specs GROUP BY 1').fetchall())
        self.assertEqual(counts['1: 0-249 words'],2)
        self.assertEqual(counts['2: 250-499 words'],2)
        self.assertEqual(counts['3: 500-999 words'],2)
        self.assertEqual(counts['4: 1000-1999 words'],2)
        self.assertEqual(counts['5: 2000+ words'],1)
        self.assertEqual(counts[None],2)
        self.assertEqual(self.con.execute('SELECT max(prior_30d_observed_commits) FROM comparison_specs').fetchone()[0],0)

    def test_same_repository_equal_weight_and_overlap(self):
        self.spec('a','large',0,100,1)
        self.spec('b','large',0,100,1)
        self.spec('c','large',1,100,0)
        self.spec('d','small',0,100,0)
        self.spec('e','small',1,100,1)
        self.spec('f','one_group_only',0,100,1)
        create_comparison_data(self.con)
        tables = comparison_tables(self.con)
        repo = tables['within_repository'].set_index('has_acceptance_criteria')
        self.assertEqual(repo.loc[0,'share_with_any_fixlike'],.5)
        self.assertEqual(repo.loc[1,'share_with_any_fixlike'],.5)
        self.assertEqual(repo.loc[0,'n_specs'],3)
        self.assertEqual(repo.loc[0,'n_repositories'],2)
        # Zero-fix observations remain in the analysis.
        self.assertEqual(tables['similar_length'].n_specs.sum(),6)

    def test_no_shared_repository_returns_empty_comparison(self):
        self.spec('a','only',0,100,0)
        create_comparison_data(self.con)
        self.assertTrue(comparison_tables(self.con)['within_repository'].empty)


if __name__ == '__main__':
    unittest.main()
