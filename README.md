PostHog engineering impact dashboard
An interactive, evidence-led shortlist of public engineering contributions. The dashboard prioritizes outcomes and supported reach rather than PR counts, commits or lines changed.

Run locally
Requires Python 3.11+ to serve the included static files. No Python packages or JavaScript build step are required.

python -m http.server 8000 --bind 127.0.0.1
Open http://127.0.0.1:8000. Select an engineer, inspect linked PR evidence, change leadership priorities, or open the methodology dialog. dashboard_data.json is committed, so visitors need no GitHub login or API calls.

Data and scope
Repository: https://github.com/PostHog/posthog
Window: 20 July–17 October 2026, complete UTC days; end-exclusive 18 October.
17,027 unique merged PRs collected; matches the initial GitHub search count.
2,007 bot-authored PRs and 17 missing-author PRs excluded from individual attribution, leaving 15,003 PRs across 193 identified human authors.
All identified human PRs remain discoverable locally, including unmatched records.
Selective evidence review covers 46 PRs grouped into 42 initiatives across 25 authors. This is distinct from complete collection.
data/ is ignored because it contains the large raw collection and checkpoints. The compact dashboard dataset includes source URLs, dates, author attribution, calculations, review coverage, and limitations. Raw data can be fetched again using the commands below; subsequent edits to GitHub descriptions may change the regenerated snapshot.

Approach
Impact means improving customer capabilities, reliability, performance, security/privacy, or engineers' ability to deliver meaningful work. Measurement and decision support are recognized within engineering enablement.

Discovery tags identify evidence to inspect, not scores. Relevant implementation excerpts and regression assertions were inspected for selected candidates. PostHog's tests and benchmarks were not independently run. Author-reported measurements remain explicitly labeled.

Each reviewed initiative receives two analyst judgments:

Dimension	Rubric
Outcome, 0–4	Unknown; small/localized; meaningful improvement; substantial obstacle or serious failure addressed; exceptional outcome with unusually strong support
Reach, 0–3	Unknown; narrow workflow; product area or multiple workflows; shared platform or documented broad population
The balanced score sums an engineer's three strongest reviewed initiatives, each scored as outcome + reach, maximum 21. Related PRs are grouped where they support one outcome. There are no additional volume points. Evidence confidence is explained separately from the numerical score.

Outcome-focused and reach-focused views use 2:1 and 1:2 weights. These test sensitivity within the reviewed evidence; they do not correct selective-review bias.

Equal scores share ranks. At the fifth-place boundary the page shows all tied contributors, rather than silently selecting a person alphabetically. In the current balanced analysis seven engineers occupy five leading positions. This is an explicit trade-off against interpreting the brief as exactly five people.

Reproduce the pipeline
GitHub CLI (gh) must be installed and authenticated for public-repository GraphQL access. Credentials stay in GitHub CLI; do not put them in repository files.

gh auth login
python fetch_prs.py
python analyze.py
python build_dashboard_data.py
The collector paginates daily searches, saves day-level checkpoints, compares retrieved counts against query counts, and checks uniqueness. Queries exceeding GitHub's search cap are split into smaller timestamp intervals. Label and linked-issue truncation is reported in the manifest. There was no such truncation in this snapshot.

analyze.py writes a complete human-PR review index and heuristic tags. It does not assign impact scores. assessments.json contains the explicit, manually curated judgments; regenerating the leaderboard does not automatically redo that review. build_dashboard_data.py validates dates, counts, authorship, score bounds and duplicate initiative membership before writing the compact dataset.

Files
fetch_prs.py: raw data collection and checkpoints.
analyze.py: discovery index and references to related work.
assessments.json: reviewed initiatives, reasoning, evidence and limitations.
build_dashboard_data.py: validation, ranking and sensitivity calculations.
dashboard_data.json: public, compact analysis snapshot.
index.html, styles.css, app.js: static interactive dashboard.
Validation
The generator validated 17,027 source PRs and all 46 assessed source PRs. JavaScript syntax and DOM-stub checks covered boundary ties and agreement with Python's weighted rankings. The user confirmed local-browser checks for engineer selection, priority changes, the complete reviewed list, the methodology dialog and GitHub links. Public hosting must be checked after deployment.

Limits
This is a reproducible shortlist of selectively reviewed public work, not a definitive performance ranking of all 193 engineers. Review depth varies. PR authorship is imperfect attribution; private work, mentoring, planning, substantive review work and shared contributions are incompletely captured. A merged PR does not prove production deployment or adoption, and small score differences do not establish overall superiority.

Assignment disclosure
The work was completed with coding-agent assistance. No reliable assignment timer was maintained, so an exact elapsed duration is unavailable. The coding-agent session export must be attached separately to the submission. The assignment's 90-minute time limit cannot be claimed as verified.