"""Build a complete review index. Discovery signals are never impact scores."""
import argparse
import collections
import csv
import datetime as dt
import json
import pathlib
import re

CATEGORIES = {
    "customer_value": [
        r"\bfeat(?:\(|:)", r"\busers?\b", r"\bcustomers?\b",
        r"\b(?:enable|unlock|unblock|introduc|support)\w*\b",
        r"\b(?:missing|new) (?:tables?|capabilit\w*|endpoints?|workflows?)\b",
    ],
    "reliability": [
        r"\bfix(?:\(|:)", r"\b(?:data loss|corrupt\w*|deadlock\w*|crash\w*|outage\w*)\b",
        r"\b(?:retry|retries|timeout\w*|deadline\w*|recovery|regression\w*)\b",
        r"\b(?:incorrect|duplicate|dropped|stalled|bounded|bounds)\b",
    ],
    "performance": [
        r"\bperf(?:\(|:)", r"\b(?:latency|speedup|faster|throughput)\b",
        r"\b(?:cache|caching|batching|serialization|memory|cpu)\b",
        r"\b(?:reduc\w*|cut\w*|improv\w*).{0,55}\b(?:cost|time|queries|load)\b",
    ],
    "security_privacy": [
        r"\b(?:security|privacy|authorization|authentication|permissions?)\b",
        r"\b(?:access control|cross[- ]tenant|cross[- ]org|scoped tokens?)\b",
        r"\b(?:polic(?:y|ies)|restrictions?|exclusions?|boundaries)\b",
        r"\b(?:oauth|redirects?|credentials?|vulnerabilit\w*|unauthori[sz]ed)\b",
    ],
    "engineering_enablement": [
        r"\b(?:devex|developer|local development|ci|tooling|build time)\b",
        r"\b(?:facade|isolation|migration|shared infrastructure|flaky)\b",
        r"\b(?:measure\w*|telemetry|instrument\w*|observability|diagnostic\w*)\b",
    ],
}

TAGS = {
    "measurement_decision_support": r"\b(?:measure\w*|telemetry|instrument\w*|observability|reports?|metrics?)\b",
    "reported_quantitative_evidence": r"\b\d+(?:\.\d+)?\s*(?:%|ms\b|seconds?\b|[x×]\b)",
    "possible_groundwork": r"\b(?:groundwork|follow[- ]up|layer [123]|pr stack|unblocks? the|prepares?)\b",
    "possible_rollout_constraint": r"\b(?:feature flag|off by default|deploy before|must deploy|experimental|rollout)\b",
}


def substantive_text(pr):
    """Strip boilerplate sections, keeping title, problem, changes and decisions."""
    body = pr.get("body") or ""
    heading = re.compile(r"(?m)^#{1,6}[ \t]+(.+?)\s*$")
    skip = False
    kept = []
    boilerplate = re.compile(
        r"how did you test|test rationale|automatic notifications|agent context|"
        r"docs update|screenshots?", re.I
    )
    for line in body.splitlines():
        match = heading.match(line)
        if match:
            skip = bool(boilerplate.search(match.group(1)))
        if not skip:
            kept.append(line)
    return pr["title"] + "\n\n" + "\n".join(kept)


def discover(text, patterns):
    hits = []
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            hits.append({
                "rule": pattern,
                "excerpt": text[max(0, match.start()-90):match.end()+180],
            })
    return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parent / "data")
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args()
    out = args.out or args.data
    out.mkdir(parents=True, exist_ok=True)
    prs = json.loads((args.data / "prs.json").read_text(encoding="utf-8-sig"))
    numbers = [pr["number"] for pr in prs]
    if len(numbers) != len(set(numbers)):
        raise ValueError("Duplicate PR numbers in source data")
    by_number = {pr["number"]: pr for pr in prs}
    known_numbers = set(by_number)
    records = []
    missing = bots = 0
    for position, pr in enumerate(prs, 1):
        if position % 2000 == 0:
            print(f"Scanned {position:,} / {len(prs):,} source PRs", flush=True)
        author = pr.get("author")
        if not author:
            missing += 1
            continue
        if author.get("__typename") == "Bot":
            bots += 1
            continue
        text = substantive_text(pr)
        matches = {name: discover(text, rules) for name, rules in CATEGORIES.items()}
        matches = {name: hits for name, hits in matches.items() if hits}
        # A reference is a connection to inspect, not proof of a single initiative.
        body = pr.get("body") or ""
        references = set(int(n) for n in re.findall(
            r"https://github\.com/PostHog/posthog/(?:pull|issues)/(\d+)\b", body, re.I
        ))
        local_body = re.sub(r"https?://\S+", "", body)
        references.update(int(n) for n in re.findall(r"(?<![\w/#])#(\d+)\b", local_body))
        references.discard(pr["number"])
        related = [
            {"number": n, "author": (by_number[n].get("author") or {}).get("login"),
             "url": by_number[n]["url"]}
            for n in sorted(references) if n in by_number
        ]
        records.append({
            "number": pr["number"], "author": author["login"],
            "title": pr["title"], "url": pr["url"], "merged_at": pr["mergedAt"],
            "candidate_categories": list(matches), "discovery_matches": matches,
            "tags": [name for name, rule in TAGS.items() if re.search(rule, text, re.I)],
            "linked_prs_in_window": related,
            "other_referenced_numbers": sorted(references - known_numbers),
            "review_status": "unreviewed",
        })
    records.sort(key=lambda row: row["number"])
    payload = {
        "purpose": "Complete human PR review index; signals are not scores or verified outcomes.",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_prs": len(prs), "excluded_bot_authored_prs": bots,
        "excluded_missing_authors": missing, "indexed_human_prs": len(records),
        "human_authors": len({r["author"] for r in records}),
        "limitations": [
            "All identified human PRs are indexed, including those with no matching signals.",
            "Discovery is heuristic. Matches may be false positives or miss meaningful work.",
            "References do not automatically group initiatives or transfer authorship credit.",
            "Quantitative tags identify reported numbers, not verified improvements.",
            "Review activity is not collected or scored.",
        ],
        "records": records,
    }
    (out / "review_index.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    fields = ["number", "author", "title", "url", "merged_at", "candidate_categories", "tags", "review_status"]
    with (out / "review_index.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in records:
            flat = {key: row[key] for key in fields}
            for key in ("candidate_categories", "tags"):
                flat[key] = "; ".join(flat[key])
            # Avoid spreadsheet formula interpretation when viewing untrusted titles.
            for key, value in flat.items():
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                    flat[key] = "'" + value
            writer.writerow(flat)
    print(f"Indexed {len(records):,} human-authored PRs from {payload['human_authors']} authors; no per-author cap.")
    for category in CATEGORIES:
        print(f"{category}: {sum(category in r['candidate_categories'] for r in records):,} matching PRs")
    print(f"No category match: {sum(not r['candidate_categories'] for r in records):,} PRs (still indexed)")
    lookup = {r["number"]: r for r in records}
    for number in (118978, 118970, 118401):
        row = lookup.get(number)
        print(f"Example #{number}: " + (", ".join(row['candidate_categories']) if row else "NOT IN SOURCE WINDOW"))
    print(f"Saved review_index.json and review_index.csv to {out}")


if __name__ == "__main__":
    main()
