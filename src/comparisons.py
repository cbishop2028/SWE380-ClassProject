"""Descriptive stratified comparisons; these are not causal estimates."""
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd


def create_comparison_data(con):
    # Materialize once: the source views otherwise repeat expensive parsing.
    con.execute("""CREATE OR REPLACE TEMP TABLE comparison_commits AS
        SELECT DISTINCT file_url_sha16, repo_name, commit_sha, commit_time,
               baseline_time, is_bot, parents_known, is_merge
        FROM commit_audit""")
    con.execute("""CREATE OR REPLACE TEMP TABLE comparison_base AS
        SELECT o.*, r.repo_name FROM spec_outcomes o
        JOIN (SELECT file_url_sha16, min(repo_name) AS repo_name
              FROM comparison_commits
              WHERE repo_name IS NOT NULL AND trim(repo_name) <> ''
              GROUP BY file_url_sha16 HAVING count(DISTINCT repo_name)=1) r
        USING (file_url_sha16)
        WHERE has_valid_baseline AND has_acceptance_criteria IN (0,1)""")
    # An event is a distinct observed human non-merge spec-touching commit.
    # Deduplicate across specification files before counting repository activity.
    con.execute("""CREATE OR REPLACE TEMP TABLE activity_timeline AS
        WITH events AS (
            SELECT DISTINCT repo_name, commit_sha, commit_time FROM comparison_commits
            WHERE NOT is_bot AND parents_known AND NOT is_merge
              AND commit_time IS NOT NULL AND commit_sha IS NOT NULL
        ), ticks AS (
            SELECT repo_name, commit_time, count(*) AS n FROM events GROUP BY 1,2
        )
        SELECT repo_name, commit_time,
               sum(n) OVER (PARTITION BY repo_name ORDER BY commit_time) AS cumulative
        FROM ticks""")
    con.execute("""CREATE OR REPLACE TEMP TABLE comparison_specs AS
        SELECT b.*,
          coalesce(upper_tick.cumulative,0)-coalesce(lower_tick.cumulative,0)
            AS prior_30d_observed_commits,
          CASE WHEN n_words IS NULL OR n_words < 0 THEN NULL
               WHEN n_words < 250 THEN '1: 0-249 words'
               WHEN n_words < 500 THEN '2: 250-499 words'
               WHEN n_words < 1000 THEN '3: 500-999 words'
               WHEN n_words < 2000 THEN '4: 1000-1999 words'
               ELSE '5: 2000+ words' END AS length_band
        FROM comparison_base b
        ASOF LEFT JOIN activity_timeline upper_tick
          ON b.repo_name=upper_tick.repo_name AND b.baseline_time > upper_tick.commit_time
        ASOF LEFT JOIN activity_timeline lower_tick
          ON b.repo_name=lower_tick.repo_name
          AND b.baseline_time - INTERVAL '30 days' > lower_tick.commit_time""")
    con.execute("""ALTER TABLE comparison_specs ADD COLUMN activity_band VARCHAR""")
    con.execute("""UPDATE comparison_specs SET activity_band =
        CASE WHEN prior_30d_observed_commits=0 THEN '1: 0 observed'
             WHEN prior_30d_observed_commits<5 THEN '2: 1-4 observed'
             WHEN prior_30d_observed_commits<20 THEN '3: 5-19 observed'
             ELSE '4: 20+ observed' END""")


def comparison_tables(con):
    repo = con.execute("""
        WITH groups AS (
          SELECT repo_name, has_acceptance_criteria, count(*) AS n_specs,
                 avg(CASE WHEN n_fixlike_later>0 THEN 1.0 ELSE 0.0 END) AS rate
          FROM comparison_specs GROUP BY 1,2
        )
        SELECT * FROM groups WHERE repo_name IN (
          SELECT repo_name FROM groups GROUP BY 1 HAVING count(*)=2)
        ORDER BY repo_name, has_acceptance_criteria
    """).df()
    # Each shared repository gets exactly the same weight in both groups.
    same_repo = repo.groupby('has_acceptance_criteria', as_index=False).agg(
        n_specs=('n_specs', 'sum'), n_repositories=('repo_name', 'count'),
        share_with_any_fixlike=('rate', 'mean'))
    tables = {'within_repository': same_repo, 'repository_detail': repo}
    for name, column in [('similar_length', 'length_band'), ('prior_activity', 'activity_band')]:
        tables[name] = con.execute(f"""
          SELECT {column} AS stratum, has_acceptance_criteria, count(*) AS n_specs,
                 sum(CASE WHEN n_fixlike_later>0 THEN 1 ELSE 0 END) AS n_with_fixlike,
                 avg(CASE WHEN n_fixlike_later>0 THEN 1.0 ELSE 0.0 END) AS share_with_any_fixlike
          FROM comparison_specs WHERE {column} IS NOT NULL GROUP BY 1,2 ORDER BY 1,2
        """).df()
    return tables


def plot_comparison(frame, title, path, grouped=False):
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = ['#477ca8', '#dc873a']
    if frame.empty:
        ax.text(.5,.5,'No comparable observations available',ha='center',transform=ax.transAxes)
    elif grouped:
        strata = sorted(frame.stratum.unique())
        for group, label in [(0, 'No acceptance criteria'), (1, 'Has acceptance criteria')]:
            part = frame[frame.has_acceptance_criteria == group].set_index('stratum')
            rates = [part.loc[s, 'share_with_any_fixlike'] if s in part.index else float('nan') for s in strata]
            positions = [i + (group-.5)*.36 for i in range(len(strata))]
            bars = ax.bar(positions, rates, width=.36, label=label, color=colors[group])
            for bar, s, rate in zip(bars, strata, rates):
                if pd.notna(rate):
                    ax.annotate(f"{rate:.1%}\nn={int(part.loc[s,'n_specs']):,}",
                                (bar.get_x()+bar.get_width()/2, rate),
                                xytext=(0,4), textcoords='offset points', ha='center', fontsize=8)
                else:
                    ax.text(bar.get_x()+bar.get_width()/2, 0, 'No data', ha='center', fontsize=8)
        ax.set_xticks(range(len(strata)), [s.split(': ',1)[1] for s in strata])
        ax.legend()
    else:
        labels = ['Has acceptance criteria' if g else 'No acceptance criteria' for g in frame.has_acceptance_criteria]
        bars = ax.bar(labels, frame.share_with_any_fixlike, color=colors)
        for bar, row in zip(bars, frame.itertuples()):
            ax.annotate(f"{row.share_with_any_fixlike:.1%}\nn={int(row.n_specs):,} specs\n{int(row.n_repositories):,} repos",
                        (bar.get_x()+bar.get_width()/2, bar.get_height()),
                        xytext=(0,4), textcoords='offset points', ha='center')
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    top = frame.share_with_any_fixlike.max() if not frame.empty else 0
    ax.set_ylim(0, min(1.2, max(.12, top*1.45 + .03)))
    ax.set_ylabel('Specifications with an observed fix-like change within 30 days')
    ax.set_title(title)
    fig.text(.5,.015,'Descriptive association; specification-file changes only. Each graph controls one factor separately.',
             ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1))
    fig.savefig(path, dpi=150)


def generate_comparisons(con, results, figures):
    create_comparison_data(con)
    tables = comparison_tables(con)
    for name, frame in tables.items():
        frame.to_csv(results / f'{name}.csv',index=False)
    for name, title in [
        ('within_repository', 'Within shared repositories (equal weight per repository)'),
        ('similar_length', 'Acceptance criteria compared within specification-length bands'),
        ('prior_activity', 'Acceptance criteria by observed repository activity before baseline')]:
        plot_comparison(tables[name], title, figures / f'{name}.png', grouped=name!='within_repository')
    con.execute("COPY (SELECT * FROM comparison_specs ORDER BY file_url_sha16) TO ? (HEADER, FORMAT CSV)",
                [str(results / 'comparison_specs.csv')])
    print('Saved within_repository, similar_length, and prior_activity graphs and CSVs.', flush=True)
