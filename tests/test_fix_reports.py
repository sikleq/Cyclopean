"""A Fixed note line says how long before it the bug was first reported, and nothing that leads to the report."""
import importlib.util
import json
import re
from pathlib import Path

from builders import fix_reports, history_view, notes_view

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location('import_fix_reports', ROOT / 'tools' / 'import_fix_reports.py')
importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(importer)

LINE = 'Abrams: Fixed Siphon not healing'
REPORTS = {'p1': {LINE: 18}}


def _pair(**kw):
    return {'thread': 123456, 'title': 'a title by a player', 'update': 'p1', 'fixed_on': '2026-01-31', 'reported': '2026-01-13',
            'line': LINE, 'why': 'same bug', **kw}


def _with_reports(monkeypatch):
    monkeypatch.setattr(fix_reports, 'fix_reports', lambda: REPORTS)


def test_the_earliest_report_of_a_line_counts():
    got = importer.days_before([_pair(), _pair(reported='2026-01-30'), _pair(reported='2026-01-01')])
    assert got == {'p1': {LINE: 30}}


def test_a_report_of_the_updates_own_day_says_nothing():
    # 'Un-zoomed sensitivity feels faster after today's patch' is dated the day of the fix it complains about
    assert importer.days_before([_pair(reported='2026-01-31')]) == {}
    assert importer.days_before([_pair(reported='2026-01-31'), _pair(reported='2026-01-30')]) == {'p1': {LINE: 1}}


def test_the_site_file_holds_a_number_and_no_trace_of_the_report():
    text = json.dumps(importer.days_before([_pair()]))
    assert '123456' not in text and 'a title' not in text and 'same bug' not in text and '2026-01-13' not in text


def test_a_hidden_row_has_no_line_to_stand_on_and_a_note_row_does():
    assert importer.days_before([{'update': 'p1', 'reported': '2026-01-13', 'fixed_on': '2026-01-31', 'row': 'X: A 1 -> 2', 'row_type': 'hidden'}]) == {}
    got = importer.days_before([{'update': '2026-01-31', 'reported': '2026-01-30', 'row': 'Fixed a thing', 'row_type': 'note'}])
    assert got == {'2026-01-31': {'Fixed a thing': 1}}


def test_a_line_the_notes_do_not_hold_is_dropped():
    kept, dropped = importer.known_only({'p1': {LINE: 18, 'Fixed nothing at all': 2}}, lambda update: {LINE})
    assert kept == {'p1': {LINE: 18}} and dropped == 1


def test_the_words_of_the_chip():
    assert fix_reports.reported_words(18) == 'was first reported 18 days before'
    assert fix_reports.reported_words(1) == 'was first reported 1 day before'


def test_the_chip_needs_the_same_update_and_line(monkeypatch):
    _with_reports(monkeypatch)
    assert 'was first reported 18 days before' in fix_reports.reported_chip('p1', f' {LINE} ')
    assert fix_reports.reported_chip('p2', LINE) == '' and fix_reports.reported_chip('p1', 'Fixed another') == ''


def test_a_patch_page_line_carries_the_chip_without_a_link(monkeypatch):
    _with_reports(monkeypatch)
    p = {'id': 'p1', 'entities': [], 'sections': [{'title': 'Heroes', 'lines': [
        {'text': LINE, 'subject': 'Abrams', 'status': 'fix', 'changes': []},
        {'text': 'Abrams: Fixed another', 'subject': 'Abrams', 'status': 'fix', 'changes': []}]}]}
    html = notes_view.notes_table(p, {}, '../')
    assert html.count('was first reported') == 1 and 'was first reported 18 days before' in html
    chip = re.search(r'<span class="reported">[^<]*</span>', html).group(0)
    assert 'href' not in chip and 'forum' not in html


def test_the_words_are_small_plain_text_not_a_caps_chip():
    css = (ROOT / 'site' / 'styles.css').read_text(encoding='utf-8')
    rule = re.search(r'\.reported \{([^}]*)\}', css).group(1)
    assert 'var(--fs-xs)' in rule and 'var(--font-ui)' in rule and 'uppercase' not in rule and 'var(--font-px)' not in rule
    assert 'chip' not in fix_reports.reported_chip.__code__.co_consts[1:] and 'class="reported"' in str(fix_reports.reported_chip.__code__.co_consts)


def test_an_interface_line_carries_it_too(monkeypatch):
    _with_reports(monkeypatch)
    html = notes_view.interface_table([{'title': 'Interface', 'lines': [{'text': LINE, 'status': 'fix'}]}], 'p1')
    assert 'was first reported 18 days before' in html


def test_an_entity_page_row_carries_it(monkeypatch):
    _with_reports(monkeypatch)
    row = {'id': 'p1', 'date': '2026-01-31', 'title': '01-31-2026 Update'}
    line = {'text': LINE, 'status': 'code', 'subject': 'Abrams', 'changes': []}
    html = history_view.history_table([('heroes.vdata:hero_atlas', 'Abrams', None)], ['Abrams'], {}, {'abrams': [(row, line)]}, '../')
    assert 'was first reported 18 days before' in html


def test_the_file_of_the_site_is_only_numbers_by_line():
    data = json.loads((ROOT / 'data' / 'fix_reports.json').read_text(encoding='utf-8'))
    assert data and all(isinstance(d, int) and d >= 0 for lines in data.values() for d in lines.values())
    text = json.dumps(data)
    assert 'forums.playdeadlock' not in text and '/threads/' not in text
