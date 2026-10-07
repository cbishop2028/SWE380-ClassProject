The code used here to compile the acceptance criteria and averages for the spec examination builds from the "SpecMine Official — 500-Repository Sample Dataset" found here: https://github.com/shyamagarwal13/specmine-official 

Therefore, the data collected for this study and converted into averages are drawn from the Sample dataset's Data Dictionary.

The table and graph labels can be explained as follows:

| Column | Type | Description |
| --- | --- | --- |
| has_acceptance_criteria | int | spec is grouped as either a 0 or a 1, where 0 means it does not have acceptance criteria and a 1 means it does |
| n_specs | int | counts the number of specs that do and don't have acceptance criteria |
| avg_words | int | averages the number of words (n_words) for the two groups |
| avg_later_commits | int | averages the number of later commits (n_later_commits) to the second decimal |
| avg_fixlike_commits | int | averages the number of fix-like commits (n_fixlike_later), which is gathered from using a filter to search for any words corresponding to "fix" |
| share_with_any_fixlike | int | calculates the portion of fix-like commits to the third decimal |
