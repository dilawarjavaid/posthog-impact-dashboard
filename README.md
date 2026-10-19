# PostHog impact dashboard — revised 57-PR subset

Run `python -m http.server 8005 --bind 127.0.0.1` and open http://127.0.0.1:8005.

This version retains the original 46 assessed PRs and adds 11 previously assessed PRs from the same 25 authors. The full collection remains 17,027 merged PRs across 90 days; all 193 identified human authors were screened. This is selective review, not assessment of every engineer.

The subset was reconstructed after submission. See subset_audit.json for the added PRs and selection rule. Rankings were recalculated without targeting the submitted leaderboard. Outcome (0–4) plus reach (0–3), summed across three strongest initiatives, gives a maximum of 21. Exactly five engineers are featured; score ties remain disclosed.

Descriptions and relevant implementation/regression excerpts were inspected. Tests and benchmarks were not independently run. No reliable assignment timer was maintained. The submitted summary must be corrected where it differs from this revision.

Keep vendor/ and all HTML, CSS, JavaScript and JSON files together when publishing. Chart.js and its license are bundled locally.
