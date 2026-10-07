import pathlib
import duckdb
import matplotlib
import matplotlib.pyplot as plt

PROJECT = pathlib.Path(__file__).resolve().parent.parent
(PROJECT / "results").mkdir(exist_ok=True)
(PROJECT / "figures").mkdir(exist_ok=True)

con = duckdb.connect(str(PROJECT / "specmine.duckdb"), read_only=True)

con.execute("""
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
           WHERE regexp_matches(lower(message), '\\b(fix|fixes|fixed|bug|hotfix|revert)\\b')
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

# Table: compare specs with vs. without acceptance criteria
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
df.to_csv(PROJECT / "results" / "acceptance_vs_fixes.csv", index=False)

# Figure: share of specs with any fix-like later commit
ax = df.plot.bar(x="has_acceptance_criteria", y="share_with_any_fixlike", legend=False)
ax.set_xlabel("Spec has acceptance criteria (0 = no, 1 = yes)")
ax.set_ylabel("Share with any fix-like later commit")
ax.set_title("Fix-like follow-up commits by acceptance criteria")
plt.tight_layout()
plt.savefig(PROJECT / "figures" / "acceptance_vs_fixes.png", dpi=150)
plt.show()
print("Saved results/acceptance_vs_fixes.csv and figures/acceptance_vs_fixes.png")