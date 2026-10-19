"""Screen every human author consistently. Triage scores are NOT impact scores."""
import argparse
import collections
import csv
import hashlib
import json
import pathlib
import re

TERMS = {
    'customer_value': ('users can', 'customers can', 'cannot query', 'could not', 'no way to', 'unblock', 'missing capability', 'new capability', 'create and', 'now supports'),
    'reliability': ('data loss', 'data corruption', 'silent corruption', 'deadlock', 'outage', 'crash', 'panic', 'stalls', 'stalled', 'memory leak', 'leaking', 'unbounded', 'failed sync', 'fails to'),
    'performance': ('latency', 'speedup', 'faster', 'throughput', 'round trip', 'round-trip', 'per-event', 'startup', 'freeze', 'freezing', 'memory spike'),
    'security_privacy': ('account takeover', 'unauthorized', 'unauthorised', 'cross-tenant', 'cross-org', 'bypass', 'access control', 'permission', 'redaction', 'text leak', 'credential', 'revoked'),
    'engineering_enablement': ('ci ', 'ci\n', 'developer', 'devex', 'local development', 'build time', 'compile time', 'shared contract', 'facade', 'telemetry', 'measurement', 'instrumentation', 'observability'),
}
SERIOUS = ('data loss', 'data corruption', 'silent corruption', 'account takeover', 'cross-tenant', 'cross-org', 'outage', 'deadlock', 'text leak', 'revoked')
TEST = re.compile(r'\b(?:regression|parameterized|assertions?|test_[a-z_]+|fails? on master|fails? before)\b', re.I)
NUMBERS = re.compile(r'(?:\d+(?:\.\d+)?\s*(?:ms\b|%|seconds?\b|mi?b\b|fps\b)|\d+\s*[→⇒]\s*\d+)', re.I)
QUANT_CONTEXT = re.compile(r'\b(?:before|after|measur\w*|benchmark\w*|profil\w*|p50|p95|p99|median)\b', re.I)


def clean_body(pr):
    skip = False
    parts = [pr['title']]
    for line in (pr.get('body') or '').splitlines():
        if re.match(r'^#{1,6}\s+', line):
            skip = bool(re.search(r'agent context|automatic notifications|docs update', line, re.I))
        if not skip:
            parts.append(line)
    return '\n'.join(parts)


def stable(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=pathlib.Path)
    parser.add_argument('--out', required=True, type=pathlib.Path)
    parser.add_argument('--assessments', type=pathlib.Path)
    args = parser.parse_args()
    prs = json.loads((args.root/'data'/'prs.json').read_text(encoding='utf-8-sig'))
    people = collections.defaultdict(list)
    for pr in prs:
        if not pr.get('author') or pr['author']['__typename'] == 'Bot':
            continue
        body = clean_body(pr)
        lower = body.lower()
        # Binary signals cap the advantage from repeated keywords or long descriptions.
        categories = {name: [term for term in terms if term in lower] for name, terms in TERMS.items()}
        categories = {name: hits for name, hits in categories.items() if hits}
        serious = [term for term in SERIOUS if term in lower]
        quantitative = bool(NUMBERS.search(body) and QUANT_CONTEXT.search(body))
        test_reference = bool(TEST.search(body))
        # Only a discovery ordering, never evidence of achieved impact.
        triage = (2*bool(serious) + int(quantitative) + int(test_reference)) if categories else 0
        people[pr['author']['login']].append({
            'number': pr['number'], 'author': pr['author']['login'], 'title': pr['title'], 'url': pr['url'],
            'categories': categories, 'serious_problem_terms': serious,
            'reported_quantitative_context': quantitative, 'regression_reference': test_reference,
            'triage_priority': triage,
            'limitation': 'Textual discovery only: may describe baseline costs, negated problems, or unverified claims.',
        })
    summaries = []
    for author, records in sorted(people.items()):
        ordered = sorted(records, key=lambda r: (-r['triage_priority'], stable(r['number'])))
        by_area = {}
        for category in TERMS:
            by_area[category] = [r for r in ordered if category in r['categories']][:2]
        summaries.append({
            'author': author, 'screened_prs': len(records),
            'triage_priority': sum(r['triage_priority'] for r in ordered[:3]),
            'top_candidates': ordered[:3], 'area_candidates': by_area,
            'candidate_areas': [name for name, candidates in by_area.items() if candidates],
            'screening_complete': True,
        })
    ordered = sorted(summaries, key=lambda r: (-r['triage_priority'], stable(r['author'])))
    nominations = []
    reasons = collections.defaultdict(list)
    # Reserve one nomination for each impact area, then fill to 15 consistently.
    for category in TERMS:
        eligible = [a for a in ordered if a['area_candidates'][category]]
        if eligible:
            leader = max(eligible, key=lambda a: (
                sum(r['triage_priority'] for r in a['area_candidates'][category]),
                a['triage_priority'], stable(a['author']),
            ))
            reasons[leader['author']].append('Area discovery priority: '+category)
            if leader not in nominations:
                nominations.append(leader)
    for author in ordered:
        if len(nominations) >= 15:
            break
        if author not in nominations:
            nominations.append(author)
            reasons[author['author']].append('Overall capped discovery priority')
    cutoff = min(row['triage_priority'] for row in nominations)
    for row in ordered:
        if row['triage_priority'] >= cutoff and row not in nominations:
            nominations.append(row)
            reasons[row['author']].append('Retained at discovery cutoff tie')
    if args.assessments:
        existing = json.loads(args.assessments.read_text(encoding='utf-8-sig'))['assessments']
        grouped = collections.defaultdict(list)
        for assessment in existing:
            grouped[assessment['author']].append(assessment)
        totals = {a: sum(sorted((i['outcome_strength']+i['reach'] for i in items), reverse=True)[:3]) for a, items in grouped.items()}
        threshold = sorted(totals.values(), reverse=True)[min(4, len(totals)-1)]
        incumbents = {a for a, score in totals.items() if score >= threshold}
        for row in summaries:
            if row['author'] in incumbents:
                reasons[row['author']].append('Current leading position: reassess on equal terms')
                if row not in nominations:
                    nominations.append(row)
    # Deliberately inspect records with no outcome-area signal as a blind-spot sample.
    unmatched = [r for records in people.values() for r in records if not r['categories']]
    unmatched_sample = sorted(unmatched, key=lambda r: stable(r['number']))[:20]
    report = {
        'status': 'Screening report only; do not publish these priorities as impact rankings.',
        'method': 'Every author screened; binary outcome/evidence terms; top-three cap; two candidates per area; five area nominations then fill to at least 15 retaining cutoff ties. Current leading positions retained for equal re-review. Hash-based ordering schedules review, not impact.',
        'limitations': ['Descriptions are untrusted evidence, not proof of outcomes.', 'Well-documented work may be easier to discover.', 'Related initiatives need manual grouping before final scoring.', 'Screening all authors is not equivalent to reviewing all authors in depth.', 'Nominations remain provisional until the unmatched sample is reviewed.'],
        'source_prs': len(prs), 'human_prs_screened': sum(len(rows) for rows in people.values()),
        'human_authors_screened': len(people), 'authors': summaries,
        'nominations': [{**row, 'selection_reasons': reasons[row['author']]} for row in nominations],
        'unmatched_count': len(unmatched), 'unmatched_audit_sample': unmatched_sample,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'screening_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (args.out/'author_screening.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['author', 'PRs screened (not scored)', 'discovery priority (not impact)', 'areas', 'candidate PRs', 'nominated'])
        for row in summaries:
            writer.writerow([row['author'], row['screened_prs'], row['triage_priority'], '; '.join(row['candidate_areas']), '; '.join(str(r['number']) for r in row['top_candidates']), row in nominations])
    print(f"Screened {report['human_prs_screened']:,} PRs across all {len(people)} identified human authors.")
    print(f'Unmatched PRs: {len(unmatched):,}; reproducible blind-spot sample: {len(unmatched_sample)}.')
    print('Provisional evidence-review nominations (not impact rankings):')
    for row in nominations:
        print(row['author'] + ': ' + ', '.join('#'+str(r['number']) for r in row['top_candidates']))


if __name__ == '__main__':
    main()
