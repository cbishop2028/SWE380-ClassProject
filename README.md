# SWE380-ClassProject

## Setup and dataset selection

Install Python and the dependencies, then download and extract the dataset from
[SpecMine on Zenodo](https://zenodo.org/records/22102780). Keep the extracted
`data/` directory and its Parquet files together. No MySQL server is needed.
Run these commands from the project root:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

For the full dataset in the sibling folder used by this project:

```bash
python run_pipeline.py --data-dir "../specmine-zenodo" --db "specmine-full.duckdb" --output-dir "outputs/full"
```

For another user's download, substitute their extracted folder path:

```bash
python run_pipeline.py --data-dir "/path/to/specmine-zenodo" --db "specmine-full.duckdb" --output-dir "outputs/full"
```

On Windows, for example, `--data-dir "C:/Users/Alex/Downloads/specmine"`.
Paths with spaces must be quoted. The release root or its `data/` subfolder is
accepted. Input paths are relative to the terminal's working directory; the
input dataset is read only. No personal path is hard-coded. The runner uses the
same Python interpreter for both steps and works on Windows, macOS, and Linux.
`bash run_pipeline.sh` accepts the same arguments.

To keep using the bundled/local sample:

```bash
python run_pipeline.py --data-dir "data/specmine-official" --db "specmine.duckdb" --output-dir "outputs/sample"
```

Without `--data-dir`, the default is `SPECMINE_DIR` if set, otherwise the sample
at `data/specmine-official`. Missing data produces an error; the loader never
silently downloads or substitutes the sample. Explicit paths are recommended
for research runs. Use `python run_pipeline.py --help` to see the options.

Only `spec_file_commits` and `spec_content_features` are loaded by default:
these are all the current analysis needs. Add `--all-tables` to import every
Parquet table, and `--include-text` to import `specs.jsonl.gz` for future text
scoring. Those options require more disk space and time.

**Use a dedicated generated database with `--db`. Rebuilding replaces its tables.**
Schema validation occurs first, and import changes are committed in one
transaction. Separate sample/full database and output paths prevent mixing their
results. Large row-level CSVs are exported directly by DuckDB rather than loaded
into pandas. Do not commit the downloaded dataset or generated databases/outputs.

To rerun analysis without rebuilding:

```bash
python src/explore.py --db "specmine-full.duckdb" --output-dir "outputs/full" --show
```

Each output directory contains `results/` and `figures/`. Its
`results/run_metadata.json` records the input directory, source table paths,
file sizes/modification times, imported row counts, DuckDB version, import time,
and the 30-day outcome definition. Retain the Zenodo record/version and original
archive with your research records; file size and modification time are not
cryptographic checksums. Older databases have unknown provenance until rebuilt.

The tested full release has 468,307 feature rows and 780,335 commit rows.
The feature table is smaller than the full specification inventory; the current
analysis includes only specifications represented in that feature table, then
excludes invalid/missing baseline timestamps from grouped comparisons.

## 30-day follow-up definition

Run automated checks with `python -m unittest discover -s tests -v`.

The baseline is the first recorded commit for each specification, ordered by
`seq_from_oldest`, before bot or merge filtering. Follow-ups must have a distinct
SHA and a valid `committed_at` timestamp strictly after the baseline and at most
30 elapsed days later. Timestamps are interpreted with their timezone offsets.
Specifications without a valid baseline timestamp are excluded from the grouped
analysis and retained with a flag in the per-spec output.

Exclude a follow-up if either author or committer has account type `Bot`, or their
login/name contains `[bot]`, the standalone word `bot`, `dependabot`, or `renovate`
(case insensitive). This heuristic cannot identify every automation account.
Exclude merge commits by multiple parent hashes, not by commit message. The
sample stores parents as comma-separated hashes; null or malformed parent data
is excluded conservatively. Empty parent strings represent root commits.

Counts deduplicate SHAs within each specification. The existing whole-word
fix-like keyword heuristic remains: fix, fixes, fixed, bug, hotfix, revert.
These are changes touching the specification file, not all implementation fixes.

`python src/explore.py` regenerates:

- `results/acceptance_vs_fixes.csv` and `figures/acceptance_vs_fixes.png`:
  group comparisons under the new filters.
- `results/commit_audit.csv`: source rows, baseline timestamps, filter flags,
  and eligibility decisions for manual validation.
- `results/spec_outcomes.csv`: per-specification counts and baseline validity.

The graph opens only with `python src/explore.py --show`.

Limitations: a zero means no observed qualifying change, not proof of no fixes.
The source does not establish a complete 30-day observation period for every
specification; incomplete follow-up remains a threat to validity. Content features
are the dataset's supplied snapshot features, not reconstructed baseline scores.
Keyword labels need manual validation, and these comparisons show association,
not causation. No ancestry-based linkage or repository-wide fix mining is added.

## Additional comparisons

The same analysis command now generates three additional graphs in the selected
`figures/` directory, with corresponding CSV tables in `results/`:

- `within_repository.png`: restricts to repositories containing both acceptance
  groups. Calculates each group's fix-like rate separately within each repository,
  then averages those rates with equal weight per repository. This uses the same
  repository weights for both groups; bar percentages are not pooled spec rates.
  `repository_detail.csv` contains each repository/group count and rate.
- `similar_length.png`: compares groups separately within preselected word-count
  bands: 0-249, 250-499, 500-999, 1000-1999, and 2000+. Missing or negative word
  counts are omitted only from this graph. Length is a snapshot feature and an
  imperfect complexity proxy. These are coarse strata, not exact matched pairs.
- `prior_activity.png`: compares groups in bands of 0, 1-4, 5-19, and 20+ observed
  human non-merge spec-touching commits in the same repository during
  `[baseline - 30 days, baseline)`. Deduplicates repository/SHA across spec files;
  excludes unknown parent metadata, invalid times, bots, and merges. It counts
  no baseline or later activity. This is an incomplete specification-activity
  proxy, NOT total repository activity or proof of inactivity. Historical coverage
  is not guaranteed for a full preceding 30 days.

`comparison_specs.csv` records included specs, repository, word-count band,
prior-activity count, and activity band. These comparisons require a valid
baseline, a 0/1 acceptance feature, and an unambiguous nonempty repository in the
spec's commit history. Unknown/ambiguous repositories are excluded. Specifications
with zero fixes or zero prior observed activity remain included. Bars show group
sample sizes; missing groups are labeled "No data", not represented as zero rates.

These graphs address each factor separately, not all factors simultaneously.
They are descriptive comparisons without confidence intervals or significance
tests. Group imbalance, repository dependence, snapshot-feature timing, incomplete
observation, and keyword-classifier errors remain limitations. They cannot support
causal conclusions. Band boundaries are fixed in code rather than chosen to
produce a particular outcome.
