"""Owner 2026-11-02: a failed site build must be seen. The build of 2026-10-26 failed unnoticed for four days."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

from build_alert import decide  # noqa: E402


def test_a_failed_build_opens_the_issue_once():
    assert decide(['failure', 'skipped'], False) == 'open'
    assert decide(['success', 'failure'], False) == 'open'        # the deploy can fail too
    assert decide(['failure', 'skipped'], True) is None


def test_only_a_whole_good_build_closes_it():
    assert decide(['success', 'success'], True) == 'close'
    assert decide(['success', 'skipped'], True) is None
    assert decide(['cancelled', 'skipped'], True) is None
    assert decide(['success', 'success'], False) is None


def test_the_workflow_runs_it_after_a_failure_with_its_own_narrow_rights():
    yml = (ROOT / '.github' / 'workflows' / 'build.yml').read_text(encoding='utf-8')
    job = yml[yml.index('  alert:'):]
    assert 'needs: [build, deploy]' in job
    assert re.search(r"if: always\(\) && github\.ref == 'refs/heads/main'", job)     # else a failure skips the job
    assert 'issues: write' in job
    assert 'issues:' not in yml[:yml.index('jobs:')]                                 # not for the whole build
    assert "join(needs.*.result, ' ')" in job and 'tools/build_alert.py' in job
