"""Reproducible 30-day outcomes from SpecMine's per-specification history."""


def create_outcome_views(con):
    """Create temporary audit/outcome views; leave source tables unchanged.

    Parents in the official sample are comma-separated hashes. Unknown or
    malformed parent metadata is excluded rather than assumed non-merge.
    """
    con.execute(r"""
    CREATE OR REPLACE TEMP VIEW commit_audit AS
    WITH normalized AS (
      SELECT *,
        TRY_CAST(committed_at AS TIMESTAMPTZ) AS commit_time,
        regexp_replace(COALESCE(parents, ''), '\s', '', 'g') AS parent_text,
        (lower(COALESCE(author_type, '')) = 'bot'
         OR lower(COALESCE(committer_type, '')) = 'bot'
         OR regexp_matches(lower(concat_ws(' ', author_login, committer_login,
                                            author_name, committer_name)),
                           '(\[bot\]|\bbot\b|\bdependabot\b|\brenovate\b)')) AS is_bot,
        regexp_matches(lower(COALESCE(message, '')),
                       '\b(fix|fixes|fixed|bug|hotfix|revert)\b') AS is_fixlike
      FROM spec_file_commits
    ), baseline AS (
      SELECT file_url_sha16, commit_time AS baseline_time,
             commit_sha AS baseline_sha
      FROM normalized
      QUALIFY row_number() OVER (
        PARTITION BY file_url_sha16 ORDER BY seq_from_oldest ASC NULLS LAST,
        commit_time ASC NULLS LAST, commit_sha
      ) = 1
    ), flags AS (
      SELECT n.*, b.baseline_time, b.baseline_sha,
        COALESCE(commit_sha <> baseline_sha
          AND commit_time > baseline_time
          AND commit_time <= baseline_time + INTERVAL '30 days', false)
          AS in_followup_window,
        parents IS NOT NULL AND (
          parent_text = '' OR regexp_full_match(parent_text,
          '[0-9a-fA-F]{40,64}(,[0-9a-fA-F]{40,64})*')) AS parents_known,
        strpos(parent_text, ',') > 0 AS is_merge
      FROM normalized n JOIN baseline b USING (file_url_sha16)
    )
    SELECT *, in_followup_window AND NOT is_bot AND parents_known
              AND NOT is_merge AND commit_sha IS NOT NULL AS eligible
    FROM flags
    """)
    con.execute("""
    CREATE OR REPLACE TEMP VIEW spec_outcomes AS
    WITH counts AS (
      SELECT file_url_sha16,
        max(baseline_time) AS baseline_time,
        count(DISTINCT commit_sha) FILTER (WHERE eligible) AS n_later_commits,
        count(DISTINCT commit_sha) FILTER (WHERE eligible AND is_fixlike)
          AS n_fixlike_later
      FROM commit_audit GROUP BY file_url_sha16
    )
    SELECT f.*, c.baseline_time,
      c.baseline_time IS NOT NULL AS has_valid_baseline,
      COALESCE(c.n_later_commits, 0) AS n_later_commits,
      COALESCE(c.n_fixlike_later, 0) AS n_fixlike_later
    FROM spec_content_features f LEFT JOIN counts c USING (file_url_sha16)
    """)
