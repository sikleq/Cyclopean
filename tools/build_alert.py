"""One open GitHub issue while the site build is broken (CI only, the last job of build.yml).

Nobody saw the build of 2026-10-26 fail, and the site stood still for four days. A failed build opens the issue, which
mentions the owner so that GitHub notifies them; the next good build closes it. Failing again adds nothing: one
notification per breakage.

    python3 tools/build_alert.py <job result> ...      env GH_TOKEN, GH_REPO, RUN_URL, OWNER
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

TITLE = 'Site build is failing'
BOT = 'github-actions[bot]'     # the name gh's --author finds; its own output says app/github-actions, which finds nothing


def decide(results: list[str], is_open: bool) -> str | None:
    """'open', 'close' or nothing. A cancelled build says nothing about the site, either way."""
    if 'failure' in results:
        return None if is_open else 'open'
    if is_open and results and all(r == 'success' for r in results):
        return 'close'
    return None


def gh(*args: str) -> str:
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True).stdout


def open_issue() -> str | None:
    rows = json.loads(gh('issue', 'list', '--state', 'open', '--author', BOT, '--limit', '100',
                         '--json', 'number,title'))
    return next((str(r['number']) for r in rows if r['title'] == TITLE), None)


def main(results: list[str]) -> int:
    number = open_issue()
    action = decide(results, number is not None)
    run = os.environ['RUN_URL']
    if action == 'open':
        gh('issue', 'create', '--title', TITLE,
           '--body', f'The site is not being updated until this is fixed.\n\n{run}\n\n@{os.environ["OWNER"]}')
    elif action == 'close':
        gh('issue', 'close', number, '--comment', f'The build works again: {run}')
    print(f'{" ".join(results)}: {action or "nothing to do"}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
