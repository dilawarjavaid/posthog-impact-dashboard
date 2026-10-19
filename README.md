# PostHog Impact Dashboard

An interactive dashboard exploring engineering impact through PostHog’s public GitHub contributions.

## Overview

The dashboard highlights five engineers based on reviewed contributions across:

- Performance
- Reliability
- Security and privacy
- Customer value
- Engineering enablement

The analysis covers 17,027 merged PRs from 20 July to 17 October 2026. All 193 identified human authors were screened, with 57 PRs across 25 engineers selectively assessed and grouped into 53 initiatives.

## Scoring

Each initiative receives an outcome score (0–4) and a supported reach score (0–3). An engineer’s balanced score combines their three strongest reviewed initiatives, with a maximum of 21 points.

PR counts, commits and lines of code earn no points. Scores reflect assessed public evidence, not a complete evaluation of individual performance.

## Features

- Interactive chart with five featured engineers
- Linked PR evidence and scoring explanations
- Outcome-focused and reach-focused weighting
- Expandable view of all 25 reviewed engineers
- Methodology dialog and downloadable analysis

## Run locally

```powershell
python -m http.server 8001 --bind 127.0.0.1
```

Open http://127.0.0.1:8001.

## Technology

Python for collection and analysis; HTML, CSS, JavaScript and Chart.js for the dashboard. Hosting uses GitHub Pages

