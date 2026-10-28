import argparse
import json
import pathlib
import sys

import duckdb
import matplotlib.pyplot as plt

from outcomes import create_outcome_views
from comparisons import generate_comparisons

PROJECT = pathlib.Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description="Analyze 30-day fix-like specification changes")
parser.add_argument("--db", type=pathlib.Path, default=PROJECT / "specmine.duckdb")
parser.add_argument("--output-dir", type=pathlib.Path, default=PROJECT)
parser.add_argument("--show", action="store_true")
args = parser.parse_args()
DB_PATH = args.db.expanduser().resolve()
FIGURES = args.output_dir / "figures"
RESULTS = args.output_dir / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

if not DB_PATH.exists():
    sys.exit(f"{DB_PATH} not found. Run python src/build_db.py first.")

con = duckdb.connect(str(DB_PATH), read_only=True)
con.execute("SET TimeZone='UTC'")
if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='pipeline_metadata'").fetchone()[0]:
    manifest = json.loads(con.execute("SELECT manifest_json FROM pipeline_metadata").fetchone()[0])
else:
    manifest = {"source_directory": "unknown (legacy database; rebuild to record source)"}
manifest.update({"database": str(DB_PATH), "followup_days": 30,
                 "outcome": "fix-like specification-file commits; bots and merges excluded"})
(RESULTS / "run_metadata.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Analyzing {DB_PATH}; source: {manifest['source_directory']}", flush=True)

create_outcome_views(con)

# Export row-level decisions and per-spec counts for manual validation.
audit_query = """
SELECT file_url_sha16, repo_name, commit_sha, seq_from_oldest, committed_at,
       baseline_sha, baseline_time, author_type, committer_type,
       author_login, committer_login, parents,
       in_followup_window, is_bot, parents_known, is_merge, is_fixlike, eligible
FROM commit_audit ORDER BY file_url_sha16, seq_from_oldest
"""
# DuckDB streams large exports directly to disk instead of collecting pandas frames.
con.execute("COPY (" + audit_query + ") TO ? (HEADER, FORMAT CSV)",
            [str(RESULTS / "commit_audit.csv")])
con.execute("COPY (SELECT * FROM spec_outcomes ORDER BY file_url_sha16) TO ? (HEADER, FORMAT CSV)",
            [str(RESULTS / "spec_outcomes.csv")])

df = con.execute("""
SELECT has_acceptance_criteria,
       COUNT(*) AS n_specs,
       ROUND(AVG(n_words)) AS avg_words,
       ROUND(AVG(n_later_commits), 2) AS avg_later_commits,
       ROUND(AVG(n_fixlike_later), 3) AS avg_fixlike_commits,
       ROUND(AVG(CASE WHEN n_fixlike_later > 0 THEN 1 ELSE 0 END), 3) AS share_with_any_fixlike
FROM spec_outcomes
WHERE has_valid_baseline
GROUP BY has_acceptance_criteria
ORDER BY has_acceptance_criteria
""").df()
print(df.to_string(index=False))
df.to_csv(RESULTS / "acceptance_vs_fixes.csv", index=False)

# Figure with readable labels and group sizes
labels = [
    f"{'Has' if row.has_acceptance_criteria == 1 else 'No'} acceptance criteria\n(n={int(row.n_specs):,})"
    for row in df.itertuples()
]
fig, ax = plt.subplots()
ax.bar(labels, df["share_with_any_fixlike"])
ax.set_ylabel("Share with any eligible fix-like commit within 30 days")
ax.set_title("30-day fix-like specification changes by acceptance criteria")
plt.tight_layout()
fig.savefig(FIGURES / "acceptance_vs_fixes.png", dpi=150)
print(f"Saved {RESULTS / 'acceptance_vs_fixes.csv'} and {FIGURES / 'acceptance_vs_fixes.png'}")

generate_comparisons(con, RESULTS, FIGURES)

# Only pop up the window if asked: python src/explore.py --show
if args.show:
    plt.show()

con.close()