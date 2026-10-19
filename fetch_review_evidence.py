"""Download a systematic review batch, reusing existing diffs."""
import argparse
import pathlib
import subprocess
import time

PRS = [71488,72631,73499,73643,73732,73954,74478,74563,75715,76654,77177,77985,78182,78518,79218,80949,81188,82910,83238,83929,84547,86792,86837,87121,88183,88224,89584,90085,90790,90841,91006,91891,92919,92971,93048,94428,95749,100148,100754,101929,103269,104404,105396,107014,107052,107422,108135,109255,109748,112933,113497,114618,114706,115960,116333,117210,117546]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=pathlib.Path)
    args = parser.parse_args()
    target = args.project / 'data' / 'evidence'
    target.mkdir(parents=True, exist_ok=True)
    downloaded = cached = 0
    for index, number in enumerate(PRS, 1):
        path = target / f'{number}.diff'
        if path.exists() and path.stat().st_size > 0:
            print(f'[{index}/{len(PRS)}] #{number} cached', flush=True)
            cached += 1
            continue
        for attempt in range(3):
            result = subprocess.run(['gh', 'pr', 'diff', str(number), '--repo', 'PostHog/posthog'], capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0 and 'diff --git ' in result.stdout:
                path.write_text(result.stdout, encoding='utf-8')
                downloaded += 1
                print(f'[{index}/{len(PRS)}] #{number} saved', flush=True)
                break
            if attempt == 2:
                raise RuntimeError(f'PR #{number}: {result.stderr[:500]}')
            time.sleep(2 ** (attempt+1))
        time.sleep(0.2)
    print(f'Complete: {downloaded} downloaded, {cached} reused. Live dashboard unchanged.')

if __name__ == '__main__':
    main()
