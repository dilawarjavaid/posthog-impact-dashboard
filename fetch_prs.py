import datetime as dt
import json
import pathlib
import subprocess
import time

REPO = "PostHog/posthog"
START = dt.date(2026, 7, 20)
END = dt.date(2026, 10, 17)
DATA = pathlib.Path(__file__).resolve().parent / "data"
CACHE = DATA / "days"

QUERY = """
query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: 50, after: $after) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number title body url createdAt mergedAt
        author { login __typename }
        additions deletions changedFiles
        labels(first: 50) {
          totalCount
          nodes { name }
        }
        closingIssuesReferences(first: 10) {
          totalCount
          nodes { number title url body }
        }
      }
    }
  }
  rateLimit { remaining resetAt }
}
"""


def graphql(query_text, after=None):
    payload = {
        "query": QUERY,
        "variables": {"q": query_text, "after": after},
    }
    last_error = ""

    for attempt in range(6):
        result = subprocess.run(
            ["gh", "api", "graphql", "--input", "-"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode == 0:
            response = json.loads(result.stdout)
            if not response.get("errors"):
                return response["data"]
            last_error = json.dumps(response["errors"])
        else:
            last_error = result.stderr

        print(f"Retry {attempt + 1}: {last_error[:250]}", flush=True)
        time.sleep(min(60, 2 ** (attempt + 1)))

    raise RuntimeError(last_error)


def fetch_interval(start, end):
    # Normalize strings before arithmetic when splitting GitHub search windows.
    if isinstance(start, str):
        start = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
    if isinstance(end, str):
        end = dt.datetime.fromisoformat(end.replace("Z", "+00:00"))
    start_text = start.isoformat().replace("+00:00", "Z")
    end_text = end.isoformat().replace("+00:00", "Z")
    query_text = (
        f"repo:{REPO} is:pr is:merged "
        f"merged:{start_text}..{end_text}"
    )
    rows = []
    after = None
    expected = None

    while True:
        response = graphql(query_text, after)
        search = response["search"]
        count = search["issueCount"]

        if count > 1000:
            if start >= end:
                raise RuntimeError("Cannot split this interval further.")
            middle = start + dt.timedelta(seconds=int((end - start).total_seconds()) // 2)
            return (
                fetch_interval(start, middle)
                + fetch_interval(middle + dt.timedelta(seconds=1), end)
            )

        if expected is None:
            expected = count
        elif count != expected:
            raise RuntimeError("Search count changed. Rerun this day.")

        nodes = search["nodes"]
        if any(not row or "number" not in row for row in nodes):
            raise RuntimeError("Search returned an unexpected or missing PR.")

        rows.extend(nodes)
        limit = response["rateLimit"]

        if limit["remaining"] < 100:
            reset = dt.datetime.fromisoformat(
                limit["resetAt"].replace("Z", "+00:00")
            )
            wait = max(
                1,
                (reset - dt.datetime.now(dt.timezone.utc)).total_seconds() + 5,
            )
            print(f"Rate limit low; waiting {wait:.0f}s.", flush=True)
            time.sleep(wait)

        if not search["pageInfo"]["hasNextPage"]:
            break
        after = search["pageInfo"]["endCursor"]
        time.sleep(0.3)

    unique = {row["number"]: row for row in rows}
    if len(unique) != expected:
        raise RuntimeError(
            f"Coverage mismatch: expected {expected}, got {len(unique)}."
        )
    return list(unique.values())


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    all_rows = []
    day = START

    while day <= END:
        path = CACHE / f"{day}.json"
        if path.exists():
            rows = json.loads(path.read_text(encoding="utf-8"))
            status = "cached"
        else:
            start = dt.datetime.combine(day, dt.time.min, dt.timezone.utc)
            end = start + dt.timedelta(days=1) - dt.timedelta(seconds=1)
            rows = fetch_interval(
                start.isoformat().replace("+00:00", "Z"),
                end.isoformat().replace("+00:00", "Z"),
            )
            temporary = path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(rows, ensure_ascii=False), encoding="utf-8"
            )
            temporary.replace(path)
            status = "fetched"

        all_rows.extend(rows)
        print(f"{day}: {len(rows)} PRs ({status})", flush=True)
        day += dt.timedelta(days=1)

    unique = {row["number"]: row for row in all_rows}
    if len(unique) != len(all_rows):
        raise RuntimeError("Duplicate PRs found across daily batches.")

    rows = sorted(unique.values(), key=lambda row: row["number"])
    (DATA / "prs.json").write_text(
        json.dumps(rows, ensure_ascii=False), encoding="utf-8"
    )
    manifest = {
        "repository": REPO,
        "start_inclusive": f"{START}T00:00:00Z",
        "end_exclusive": f"{END + dt.timedelta(days=1)}T00:00:00Z",
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "days": (END - START).days + 1,
        "unique_merged_prs": len(rows),
        "daily_counts_validated": True,
        "labels_truncated_prs": [
            row["number"] for row in rows
            if row["labels"]["totalCount"] > len(row["labels"]["nodes"])
        ],
        "linked_issues_truncated_prs": [
            row["number"] for row in rows
            if row["closingIssuesReferences"]["totalCount"]
            > len(row["closingIssuesReferences"]["nodes"])
        ],
    }
    (DATA / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"\nComplete: {len(rows)} unique PRs saved to data/prs.json")


if __name__ == "__main__":
    main()
