import numbers
import pathlib
import sys

import duckdb
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Settings for Sprint 2
# ---------------------------------------------------------------------------
WINDOW_DAYS = 30           # only count commits within this many days of the spec's first commit
TIGHT_SPECS = True         # drop tiny / placeholder / lorem-ipsum specs (template junk)

PROJECT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = PROJECT / "specmine.duckdb"
FIGURES = PROJECT / "figures"
RESULTS = PROJECT / "results"
RESULTS.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)

if not DB_PATH.exists():
    sys.exit(f"{DB_PATH} not found. Run `python src/build_db.py` first.")

con = duckdb.connect(str(DB_PATH), read_only=True)


def sql(query):
    """Fill in the settings above, then run the query."""
    query = query.replace("WINDOW_DAYS", str(WINDOW_DAYS))
    return con.execute(query)


# 1. Clean up each commit: parse the date, count parents, flag merges and bots
sql(r"""
CREATE TEMP VIEW commits AS
SELECT
    file_url_sha16,
    seq_from_oldest,
    message,
    -- dates look like 2024-04-03T14:11:47Z
    TRY_CAST(replace(left(committed_at, 19), 'T', ' ') AS TIMESTAMP) AS committed_ts,
    -- a merge commit has 2+ parent commits
    len(regexp_extract_all(coalesce(parents, ''), '[0-9a-f]{40}')) >= 2
      OR regexp_matches(lower(coalesce(message, '')),
                        '^merge (pull request|branch|remote-tracking branch)') AS is_merge,
    -- bot accounts: GitHub marks them as type 'Bot' and/or with a [bot] suffix
    coalesce(author_type, '') = 'Bot'
      OR lower(coalesce(author_login, '')) LIKE '%[bot]%'
      OR lower(coalesce(author_name, '')) LIKE '%[bot]%' AS is_bot
FROM spec_file_commits
""")

# 2. When was each spec created? (its first commit)
sql(r"""
CREATE TEMP VIEW spec_start AS
SELECT file_url_sha16,
       MIN(seq_from_oldest) AS first_seq,
       arg_min(committed_ts, seq_from_oldest) AS created_at
FROM commits
GROUP BY file_url_sha16
""")

# 3. Only keep specs that were created at least WINDOW_DAYS before the data ends
sql(r"""
CREATE TEMP VIEW eligible_specs AS
SELECT s.*
FROM spec_start s
WHERE s.created_at IS NOT NULL
  AND s.created_at <= (SELECT MAX(committed_ts) FROM commits) - INTERVAL WINDOW_DAYS DAY
""")

# 4. Later commits that pass all three rules
sql(r"""
CREATE TEMP VIEW later_commits AS
SELECT c.*,
       c.committed_ts <= s.created_at + INTERVAL WINDOW_DAYS DAY AS in_window
FROM commits c
JOIN eligible_specs s USING (file_url_sha16)
WHERE c.seq_from_oldest > s.first_seq
""")

sql(r"""
CREATE TEMP VIEW later AS
SELECT file_url_sha16,
       COUNT(*) AS n_later_commits,
       COUNT(*) FILTER (
         WHERE regexp_matches(lower(coalesce(message, '')),
                              '\b(fix|fixes|fixed|bug|hotfix|revert)\b')
       ) AS n_fixlike_later
FROM later_commits
WHERE in_window AND NOT is_merge AND NOT is_bot
GROUP BY file_url_sha16
""")

# 5. Join to the spec features and quality scores
spec_filter = """
  AND f.is_tiny = 0
  AND f.has_unfilled_placeholder = 0
  AND f.has_lorem = 0
""" if TIGHT_SPECS else ""

sql(rf"""
CREATE TEMP VIEW spec_outcomes AS
SELECT f.*,
       q.spec_quality_score,
       q.ac_score,
       q.scenario_score,
       q.file_ref_score,
       COALESCE(l.n_later_commits, 0) AS n_later_commits,
       COALESCE(l.n_fixlike_later, 0) AS n_fixlike_later
FROM spec_content_features f
JOIN eligible_specs e USING (file_url_sha16)
LEFT JOIN spec_quality_scores q USING (file_url_sha16)
LEFT JOIN later l USING (file_url_sha16)
WHERE TRUE {spec_filter}
""")

# How many commits each rule removed
print(f"\nCommit filtering ({WINDOW_DAYS}-day window, merges and bots removed):")
filt = sql(r"""
SELECT COUNT(*)                                         AS later_commits_total,
       COUNT(*) FILTER (WHERE NOT in_window)           AS outside_window,
       COUNT(*) FILTER (WHERE in_window AND is_merge)  AS merges_removed,
       COUNT(*) FILTER (WHERE in_window AND NOT is_merge AND is_bot) AS bots_removed,
       COUNT(*) FILTER (WHERE in_window AND NOT is_merge AND NOT is_bot) AS commits_kept,
       COUNT(*) FILTER (WHERE committed_ts IS NULL)    AS unparseable_dates
FROM later_commits
""").df()
print(filt.to_string(index=False))

# Main results table
df = sql(r"""
SELECT has_acceptance_criteria,
       COUNT(*) AS n_specs,
       ROUND(AVG(n_words)) AS avg_words,
       ROUND(AVG(n_later_commits), 2) AS avg_later_commits,
       ROUND(AVG(n_fixlike_later), 3) AS avg_fixlike_commits,
       ROUND(AVG(CASE WHEN n_fixlike_later > 0 THEN 1 ELSE 0 END), 3) AS share_with_any_fixlike,
       ROUND(SUM(n_fixlike_later) / NULLIF(SUM(n_later_commits), 0), 3) AS fix_rate
FROM spec_outcomes
GROUP BY has_acceptance_criteria
ORDER BY has_acceptance_criteria
""").df()
print("\nResults:")
print(df.to_string(index=False))

suffix = f"{WINDOW_DAYS}d"
csv_path = RESULTS / f"acceptance_vs_fixes_{suffix}.csv"
png_path = FIGURES / f"acceptance_vs_fixes_{suffix}.png"
df.to_csv(csv_path, index=False)

labels = [
    f"{'Has' if row.has_acceptance_criteria == 1 else 'No'} acceptance criteria\n(n={int(row.n_specs):,})"
    for row in df.itertuples()
]
fig, ax = plt.subplots()
ax.bar(labels, df["share_with_any_fixlike"])
ax.set_ylabel(f"Share with a fix-like commit within {WINDOW_DAYS} days")
ax.set_title("Fix-like follow-up commits by acceptance criteria\n(merge and bot commits excluded)")
plt.tight_layout()
fig.savefig(png_path, dpi=150)

# Pop-up table window
table_path = FIGURES / f"results_table_{suffix}.png"

def draw_table(ax, frame, title):
    ax.axis("off")
    ax.set_title(title, fontweight="bold", loc="left")
    def fmt(v):
        if isinstance(v, numbers.Real) and float(v).is_integer():
            return f"{int(v):,}"
        return f"{v:g}" if isinstance(v, numbers.Real) else str(v)

    cells = [[fmt(v) for v in row] for row in frame.itertuples(index=False)]
    headers = [c.replace("_", "\n") for c in frame.columns]
    t = ax.table(cellText=cells, colLabels=headers, loc="upper center", cellLoc="center")
    t.auto_set_font_size(False)
    t.set_fontsize(9)
    t.scale(1, 2.2)
    for (r, _), cell in t.get_celld().items():
        if r == 0:
            cell.set_facecolor("#dbe7f3")
            cell.set_height(cell.get_height() * 1.6)

table_fig, (ax_res, ax_filt) = plt.subplots(2, 1, figsize=(11, 5),
                                            gridspec_kw={"height_ratios": [3, 2]})
table_fig.canvas.manager.set_window_title("Results table")
shown = df.copy()
shown["has_acceptance_criteria"] = shown["has_acceptance_criteria"].map({0: "No", 1: "Yes"})
draw_table(ax_res, shown, f"Acceptance criteria vs. fix-like commits ({WINDOW_DAYS}-day window)")
draw_table(ax_filt, filt.astype(int), "Commit filtering")
table_fig.tight_layout()
table_fig.savefig(table_path, dpi=150, bbox_inches="tight")

print(f"\nSaved {csv_path}\n      {png_path}\n      {table_path}")

# Rubric Summary Evaluation
print("\n" + "=" * 80)
print("SPECIFICATION QUALITY RUBRIC EVALUATION SUMMARY")
print("=" * 80)

rubric_summary_df = sql(r"""
SELECT 
    COUNT(q.file_url_sha16) AS total_scored_specs,
    ROUND(AVG(q.spec_quality_score), 4) AS avg_overall_score,
    ROUND(AVG(q.ac_score), 4) AS avg_acceptance_criteria_score,
    ROUND(AVG(q.scenario_score), 4) AS avg_scenario_score,
    ROUND(AVG(q.file_ref_score), 4) AS avg_file_ref_score
FROM spec_quality_scores q
""").df()

print("\n--- Dimension Scores Across Dataset ---")
print(rubric_summary_df.to_string(index=False))

tier_df = sql(r"""
SELECT 
    CASE 
        WHEN spec_quality_score >= 0.7 THEN 'High Quality (0.7 - 1.0)'
        WHEN spec_quality_score >= 0.3 THEN 'Medium Quality (0.3 - 0.7)'
        ELSE 'Low Quality (0.0 - 0.3)'
    END AS quality_tier,
    COUNT(*) AS n_specs,
    ROUND(AVG(spec_quality_score), 3) AS avg_tier_score,
    ROUND(AVG(n_later_commits), 2) AS avg_later_commits,
    ROUND(AVG(n_fixlike_later), 3) AS avg_fixlike_commits,
    ROUND(AVG(CASE WHEN n_fixlike_later > 0 THEN 1 ELSE 0 END), 3) AS share_with_any_fixlike
FROM spec_outcomes
WHERE spec_quality_score IS NOT NULL
GROUP BY quality_tier
ORDER BY avg_tier_score DESC
""").df()

print("\n--- Fix Outcomes Grouped by Rubric Quality Tier ---")
print(tier_df.to_string(index=False))

detailed_export_df = sql(r"""
SELECT 
    file_url_sha16,
    spec_quality_score,
    ac_score,
    scenario_score,
    file_ref_score,
    n_later_commits,
    n_fixlike_later
FROM spec_outcomes
WHERE spec_quality_score IS NOT NULL
""").df()

rubric_csv_path = RESULTS / f"rubric_scores_detailed_{WINDOW_DAYS}d.csv"
detailed_export_df.to_csv(rubric_csv_path, index=False)
print(f"\nSaved detailed rubric scores with fix outcomes to: {rubric_csv_path}")

if "--no-show" not in sys.argv:
    plt.show()
