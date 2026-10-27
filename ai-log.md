This pdf file is the description of a project that I have worked on for a little while. Sprint 1 is complete. The two .py files are the pipeline that builds the database and explores and graphs the data for the project. This was the feedback given to my group by our professor: "For Sprint 2, the group should expand the quality score beyond acceptance criteria, define “downstream fix” more rigorously, and use a statistical model or controlled comparison rather than averages alone. They should also connect the findings to a concrete AI-assisted acceptance-review tool or workflow, to help with understanding what type of acceptance criteria tend to be more impactful if applicable. You can have AI help with taxonomizing these acceptance criteria and extract what "really matters"" Could you show me in a step-by-step way how to move forward with sprint 2? We have selected problem 8 from the project description file.

Read and updated memory
Sprint 2 is due Oct 28, two days from now, so I’ve ordered the steps by what the professor’s feedback and the Sprint 2 rubric need most. Anything marked “can slip to Sprint 3” can wait.

Step 0: Backlog and process (30 min)
The Sprint 2 rubric grades process as well as code. Create issues, each with an owner and an acceptance criterion, for steps 1-6 below. Put them under a “Sprint 2” milestone. Plan for at least one PR reviewed by someone other than its author, plus a retrospective entry. These are easy points, so do them first.

Step 1: Define “downstream fix” rigorously
Right now the outcome is “any later commit to the spec file whose message matches fix|bug|revert…”. That has three problems you should name in the report:

It measures edits to the spec, not problems in the code. A “fix” commit touching a spec file is really spec churn.
Exposure time differs. Old specs have had more time to collect commits, so you need a fixed window.
The regex is noisy. It matches things like “fix typo”, “bugfix release notes” and merge commits.
A tighter definition:

Primary outcome: a fix-like commit within W days (try 30 and 90) after the spec’s first commit.
Cleaner matching: exclude merge commits and bot commits. Treat “fix typo/formatting/lint” as non-fix. Also match conventional-commit prefixes like fix: and fix(scope):.
Secondary outcomes (sensitivity checks): the count of fix-like commits, and time-to-first-fix.
If the dataset links specs to PRs or issues (run DESCRIBE on every table to check), add “linked PR/issue later closed as bug” as a stronger outcome.
Validate the definition. Have two members independently label about 100 random commits as fix or not fix. Report the regex’s precision and recall and Cohen’s kappa between labelers. This doubles as your required validation sample.
Step 2: Expand the quality score beyond acceptance criteria
Extract several feature groups into spec_content_features, or a new table built by a new src/features.py:

Dimension	Example features
Acceptance criteria	count, Given/When/Then, checkbox items, SHALL/MUST wording
Scenarios	count of scenario blocks, edge-case or error scenarios
Traceability	file path references, links to issues or PRs
Completeness	placeholders (TODO/TBD/[NEEDS CLARIFICATION]), unchecked tasks
Structure	number of headings, task list present, length
Write the rubric down before looking at outcomes, for example 0-2 points per dimension, and call it the a priori score. Then fit a data-driven model (step 4) and compare. That gives you the “baseline vs. improved” comparison the rubric asks for.

Step 3: Taxonomize acceptance criteria with AI
This is the professor’s “what really matters” suggestion.

Extract the acceptance-criteria blocks and sentences from spec_text with regex. Parse headings like “Acceptance Criteria”, bullet lists under them, and Given/When/Then lines.
Draft a codebook with 6-10 categories, for example: observable behavior, quantitative threshold, error or edge case, non-functional (performance, security), UI or output format, data or API contract, testable command, and vague or subjective (“works well”).
Label with an LLM at temperature 0, with the model version pinned, the prompt saved in the repo, and results cached to a file so the run is reproducible. Add each use to ai-use-log.md.
Validate by hand. Label about 100 criteria yourselves and report agreement with the LLM. Revise the codebook where they disagree. The rubric wants AI output verified, not trusted.
Make per-spec features like n_edge_case_criteria or share_vague_criteria. These feed the model in step 4.
Step 4: Replace averages with a statistical model
The Sprint 1 comparison confounds acceptance criteria with spec length, repo, and age. A suggested approach, in order of priority:

Logistic regression on fix_within_W. Predictors are the quality-score components, with log(n_words), repo size or activity, tool family, and spec age as controls. Use cluster-robust standard errors by repo, since specs in the same repo aren’t independent. Report odds ratios with 95% CIs.
A controlled comparison: within each repo, compare specs with and without acceptance criteria, or match specs on length and tool family. This addresses confounding directly.
A tree-based baseline (gradient boosting) with permutation importance, to see which features matter most, including the taxonomy categories from step 3. Use a train/test split.
Optional, can slip to Sprint 3: a Cox time-to-first-fix model to handle censoring, and a count model with log-exposure offset.
A sketch of step 1:

python
import statsmodels.formula.api as smf

m = smf.logit(
    "fix_within_90 ~ has_acceptance_criteria + n_ac_items + n_scenarios "
    "+ n_file_refs + n_placeholders + np.log(n_words) + C(tool_family)",
    data=df
).fit(cov_type="cluster", cov_kwds={"groups": df["repo_id"]})
print(m.summary())
(Check actual column names with con.execute("DESCRIBE spec_content_features").)

Write up the correlation-vs-causation discussion explicitly. Possible confounders are mature teams writing both better specs and fewer fixes, and larger specs being both more detailed and more likely to be revised.

Step 5: Build the acceptance-review tool
A small, concrete deliverable could be src/review_spec.py, a CLI that takes a spec file and outputs:

the quality score and its per-dimension breakdown,
missing elements, such as no edge-case criteria or placeholders left,
each acceptance criterion’s taxonomy category, with vague ones flagged,
an optional LLM-suggested rewrite of the vague criteria,
the evidence behind each flag, for example “specs without edge-case criteria had 1.4x the odds of a fix-like commit (CI …)”. Fill the numbers in from your actual step 4 results.
Output a markdown report. A GitHub Action that comments this on PRs touching spec files can be a future-work note. A demo on two or three real specs, one good and one weak, makes a good case study.

Step 6: Tests, reproducibility, report
Tests (tests/): unit tests for the fix-commit classifier, the acceptance-criteria extractor, and the score function, using small hand-written examples. This is a Sprint 2 requirement.
Pipeline: add the new scripts to run_pipeline.sh so one command regenerates all tables and figures.
Report: update the Background, Method, Implementation, and Preliminary Results sections. Add the new outcome definition, rubric, and codebook to DATA_DICTIONARY.md, and the confounders to THREATS_TO_VALIDITY.md.
Retrospective: record the changes: outcome redefined, score expanded, averages replaced by a model, tool added.
Suggested schedule
Today (Oct 26): step 0, then steps 1 and 2 (outcome and features), and start labeling commits.
Tomorrow (Oct 27): steps 3 and 4 (taxonomy and models), plus tests as you go.
Morning of Oct 28: step 5 (a minimal tool), the report update, a PR review, and the retrospective.
If time gets tight, cut the Cox model, the count model, and the tool’s LLM rewrite suggestions. A minimal version of everything else is what the feedback asks for.

A small bug to fix in explore.py
The end of the file calls plt.show() unconditionally and prints the “Saved” line twice, which defeats the --show guard. It will block when run in a pipeline. Delete the last print(...) and plt.show() and keep the guarded version.

If you want, tell me the table schemas (the DESCRIBE output) and I can write the feature extractor and the outcome-labeling code for you.
