import pathlib
import sys

import duckdb
import matplotlib.pyplot as plt

PROJECT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = PROJECT / "specmine.duckdb"
FIGURES = PROJECT / "figures"
RESULTS = PROJECT / "results"
RESULTS.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)

if not DB_PATH.exists():
    sys.exit(f"{DB_PATH} not found. Run `python src/build_db.py` first.")

con = duckdb.connect(str(DB_PATH), read_only=True)

con.execute(r"""
CREATE TEMP VIEW spec_outcomes AS
WITH ranked AS (
  SELECT file_url_sha16, message, seq_from_oldest,
         MIN(seq_from_oldest) OVER (PARTITION BY file_url_sha16) AS first_seq
  FROM spec_file_commits
),
later AS (
  SELECT file_url_sha16,
         COUNT(*) AS n_later_commits,
         COUNT(*) FILTER (
           WHERE regexp_matches(lower(message), '\b(fix|fixes|fixed|bug|hotfix|revert)\b')
         ) AS n_fixlike_later
  FROM ranked
  WHERE seq_from_oldest > first_seq
  GROUP BY file_url_sha16
)
SELECT f.*,
       COALESCE(l.n_later_commits, 0) AS n_later_commits,
       COALESCE(l.n_fixlike_later, 0) AS n_fixlike_later
FROM spec_content_features f
LEFT JOIN later l USING (file_url_sha16)
""")

df = con.execute("""
SELECT has_acceptance_criteria,
       COUNT(*) AS n_specs,
       ROUND(AVG(n_words)) AS avg_words,
       ROUND(AVG(n_later_commits), 2) AS avg_later_commits,
       ROUND(AVG(n_fixlike_later), 3) AS avg_fixlike_commits,
       ROUND(AVG(CASE WHEN n_fixlike_later > 0 THEN 1 ELSE 0 END), 3) AS share_with_any_fixlike
FROM spec_outcomes
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
ax.set_ylabel("Share with any fix-like later commit")
ax.set_title("Fix-like follow-up commits by acceptance criteria")
plt.tight_layout()
fig.savefig(FIGURES / "acceptance_vs_fixes.png", dpi=150)
print(f"Saved {RESULTS / 'acceptance_vs_fixes.csv'} and {FIGURES / 'acceptance_vs_fixes.png'}")

# Only pop up the window if asked: python src/explore.py --show
if "--show" in sys.argv:
    plt.show()
    
print(f"Saved {RESULTS / 'acceptance_vs_fixes.csv'}")
plt.show()