"""Validate reviewed assessments and build a compact provisional leaderboard."""
import argparse
import collections
import datetime as dt
import json
import pathlib


def rank(authors, outcome_weight=1, reach_weight=1):
    rows = []
    for author, initiatives in authors.items():
        selected = sorted(
            initiatives,
            key=lambda x: (-(outcome_weight*x['outcome_strength'] + reach_weight*x['reach']), x['initiative']),
        )[:3]
        rows.append({
            'author': author,
            'score': sum(outcome_weight*x['outcome_strength'] + reach_weight*x['reach'] for x in selected),
            'reviewed_initiative_count': len(initiatives),
            'counted_initiatives': selected,
        })
    rows.sort(key=lambda x: (-x['score'], x['author'].lower()))
    last = None
    for position, row in enumerate(rows, 1):
        if row['score'] != last:
            current_rank = position
        row['rank'] = current_rank
        last = row['score']
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent)
    parser.add_argument('--assessments', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    root = args.root
    document = json.loads((args.assessments or root/'assessments.json').read_text(encoding='utf-8-sig'))
    source = json.loads((root/'data'/'prs.json').read_text(encoding='utf-8-sig'))
    manifest = json.loads((root/'data'/'manifest.json').read_text(encoding='utf-8-sig'))
    lookup = {pr['number']: pr for pr in source}
    if len(lookup) != len(source) or len(source) != manifest['unique_merged_prs']:
        raise ValueError('Source uniqueness or manifest count mismatch')
    start = dt.datetime.fromisoformat(manifest['start_inclusive'].replace('Z', '+00:00'))
    end = dt.datetime.fromisoformat(manifest['end_exclusive'].replace('Z', '+00:00'))
    for pr in source:
        merged = dt.datetime.fromisoformat(pr['mergedAt'].replace('Z', '+00:00'))
        if not start <= merged < end:
            raise ValueError(f"PR #{pr['number']} is outside the analysis window")
    authors = collections.defaultdict(list)
    used = set()
    for assessment in document['assessments']:
        if type(assessment['outcome_strength']) is not int or not 0 <= assessment['outcome_strength'] <= 4:
            raise ValueError('Invalid outcome score')
        if type(assessment['reach']) is not int or not 0 <= assessment['reach'] <= 3:
            raise ValueError('Invalid reach score')
        evidence = []
        for number in assessment['prs']:
            if number in used:
                raise ValueError(f'PR #{number} counted in multiple initiatives')
            used.add(number)
            pr = lookup[number]
            if not pr.get('author') or pr['author']['login'] != assessment['author']:
                raise ValueError(f'Author mismatch for PR #{number}')
            evidence.append({'number': number, 'title': pr['title'], 'url': pr['url'], 'merged_at': pr['mergedAt']})
        enriched = {**assessment, 'score': assessment['outcome_strength'] + assessment['reach'], 'sources': evidence}
        authors[assessment['author']].append(enriched)
    human = [pr for pr in source if pr.get('author') and pr['author']['__typename'] != 'Bot']
    balanced = rank(authors)
    outcome = rank(authors, 2, 1)
    reach = rank(authors, 1, 2)
    payload = {
        'status': 'Provisional ranking among reviewed engineers; evidence review is selective.',
        'coverage': {**manifest, 'human_authored_prs': len(human),
                     'human_authors': len({pr['author']['login'] for pr in human}),
                     'reviewed_prs': len(used), 'reviewed_authors': len(authors),
                     'reviewed_initiatives': len(document['assessments'])},
        'methodology': {
            'formula': 'Sum of the three strongest reviewed initiative scores; each = outcome (0–4) + reach (0–3). Maximum 21.',
            'ties': 'Equal scores receive equal ranks. Alphabetical display order is not a tie-break judgment.',
            'limitations': document['review_limitations'],
            'evidence': 'Relevant diff excerpts inspected; tests and benchmarks not independently executed.',
            'confidence': 'Reported measurements are labeled separately; scores are analyst judgments, not measured business impact.',
        },
        'engineers': balanced,
        'sensitivity': {
            'outcome_focused': [{'author': r['author'], 'rank': r['rank']} for r in outcome],
            'reach_focused': [{'author': r['author'], 'rank': r['rank']} for r in reach],
            'limitation': 'Only tests weights within reviewed evidence; does not correct selection or review-depth bias.',
        },
    }
    target = args.output or root/'dashboard_data.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Validated {len(source):,} source PRs and {len(used)} assessed PRs.')
    print(f'Reviewed {len(document["assessments"])} initiatives across {len(authors)} authors.')
    for row in balanced[:8]:
        print(f"{row['rank']:>2}. {row['author']}: {row['score']}/21 ({row['reviewed_initiative_count']} reviewed initiatives)")
    print(f'Saved {target}')


if __name__ == '__main__':
    main()
