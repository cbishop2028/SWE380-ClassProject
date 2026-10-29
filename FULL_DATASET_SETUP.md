# Running the analysis on the full SpecMine dataset (Sprint 2)

Sprint 1 used the 500-repository sample (~28,500 specs). Sprint 2 uses the full
SpecMine release (~470,000 specs). The analysis only needs **two** files from it.

## 1. Prerequisites (one time)

- **Python 3.11+** from python.org. On Windows, tick **"Add python.exe to PATH"** in the installer.
- The project's packages. From the project folder (the one with `README.md` and `src`):
  ```
  python -m pip install -r requirements.txt
  ```
  If `python` isn't recognized on Windows, use `py` instead of `python` everywhere below.

## 2. Download the full dataset

1. Go to the SpecMine dataset on Hugging Face: https://huggingface.co/datasets/ShyAgarwal/specmine
2. Click the **"Files and versions"** tab, then open the **`data`** folder.
3. Download **only** these two files (click the download icon ↓ next to each one):

   | File | Size |
   |---|---|
   | `spec_content_features.parquet` | ~11 MB |
   | `spec_file_commits.parquet` | ~423 MB |

   (Optional: `DATA_DICTIONARY.md` explains every column.)

4. Put them in a folder **outside** the project, exactly like this:
   ```
   C:\specmine-full\
       data\
           spec_content_features.parquet
           spec_file_commits.parquet
   ```
   Don't put anything else in `C:\specmine-full\data` (especially not the sample's files).
   File names must match exactly; the scripts use them as table names.
   Your browser saves downloads to your Downloads folder, so move them here afterward. If Windows renamed a file
   (for example `spec_file_commits (1).parquet`), rename it back.

**Backup option: Zenodo.** If Hugging Face isn't working, the same files are in the SpecMine
Zenodo record (https://doi.org/10.5281/zenodo.22102779). Zenodo only offers the whole release
as one large zip (several GB). Download it, double-click it to open it in File Explorer, copy the
two files out of `specmine-zenodo\data`, then delete the zip.

## 3. Update the code

Replace these two files in the project with the Sprint 2 versions:

- `src/build_db.py`: reads the Parquet files directly (no huge database copy) and
  no longer requires `specs.jsonl.gz`.
- `src/explore.py`: 30-day window, merge and bot commits removed, template specs removed,
  adds `fix_rate`, and pops up a results table and a bar chart.

Then delete `specmine.duckdb` in the project folder if it exists (it was built from the sample).

## 4. Run it

Open Command Prompt **in the project folder** (in File Explorer, click the address bar,
type `cmd`, and press Enter), then run:

```
set SPECMINE_DIR=C:\specmine-full
python src\build_db.py
python src\explore.py
```

- **PowerShell** (prompt starts with `PS`): use `$env:SPECMINE_DIR = "C:\specmine-full"` instead of `set ...`.
- **Mac/Linux:** `export SPECMINE_DIR=~/specmine-full`, then `python3 src/build_db.py` and `python3 src/explore.py`.
- `SPECMINE_DIR` only lasts for that terminal window. If you skip it, the scripts fall back to the 500-repo sample.

### What you should see

- `build_db.py` prints `Using data from C:\specmine-full`, then **two** tables with large row counts,
  and `spec_text: skipped`.
  If you see ~28,583 rows for `spec_content_features` or tables like `kiro_repos`, you're
  pointing at the **sample**, not the full dataset.
- `explore.py` prints two tables and opens two windows (the results table and the bar chart). Close them to finish.
  Use `python src\explore.py --no-show` to skip the pop-ups.

Outputs (these don't overwrite the Sprint 1 files):

- `results\acceptance_vs_fixes_30d.csv`
- `figures\acceptance_vs_fixes_30d.png`: the bar chart
- `figures\results_table_30d.png`: the table image

## Settings

At the top of `src/explore.py`:

- `WINDOW_DAYS = 30`: only count commits within this many days of the spec's first commit.
- `TIGHT_SPECS = True`: drop tiny, unfilled-template, and lorem-ipsum specs.

## Troubleshooting

| Problem | Fix |
|---|---|
| `pip is not recognized` | Use `python -m pip ...` (or `py -m pip ...`) |
| `No such file or directory: requirements.txt` | You're in the wrong folder; `cd` into the one containing `requirements.txt` (the zip often nests a folder of the same name) |
| `The system cannot find the path specified` | Command Prompt doesn't understand `~`; copy the path from File Explorer's address bar |
| Results identical to the sample | `SPECMINE_DIR` isn't set in this window, or `C:\specmine-full\data` contains the sample's files |
| `Table ... does not exist` | A Parquet file is misnamed (check for a ` (1)` added by the browser); it must be exactly `spec_file_commits.parquet` / `spec_content_features.parquet` |
