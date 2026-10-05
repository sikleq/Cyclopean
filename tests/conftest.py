"""Shared fixtures. `browser`: headless Chromium for the tests of site/scripts.js and styles.css. On a developer's
machine without Playwright or its Chromium those tests skip; in CI (the `CI` variable GitHub Actions sets) a missing
browser is a failure — the 22 browser tests had skipped there for good, so 1,700 lines of scripts.js went untested
(review 2026-10-05)."""
import os

import pytest


def _sync_api():
    if os.environ.get('CI'):
        from playwright import sync_api        # CI installs it (.github/workflows/build.yml): never a silent skip
        return sync_api
    return pytest.importorskip('playwright.sync_api')


@pytest.fixture(scope='module')
def browser():
    sync_api = _sync_api()
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as e:                  # no browser downloaded: not this test's business, except in CI
            if os.environ.get('CI'):
                raise
            pytest.skip(f'no Chromium for Playwright: {e}')
        yield b
        b.close()
