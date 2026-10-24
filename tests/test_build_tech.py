"""Fuller build pages (2026-10-24): files per hero, protobuf messages, binary strings, functions of the DLLs."""
import importlib.util
from pathlib import Path

from builders import build_tech
from pipeline import extras, protobuf_diff, strings_diff

_spec = importlib.util.spec_from_file_location(
    'import_dll_summary', Path(__file__).resolve().parent.parent / 'tools' / 'import_dll_summary.py')
ids = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ids)

PROTO_OLD = '''
message CSOCitadelParty {
\toptional uint64 party_id = 1; // the id
\toneof kind {
\t\tbool solo = 14;
\t}
\toptional bool is_high_skill_range_party = 13;
\tmessage Member { optional uint32 account_id = 1; }
}
enum EStat { k_A = 0; }
'''
PROTO_NEW = '''
message CSOCitadelParty {
\toptional uint64   party_id = 1;
\toneof kind {
\t\tbool solo = 15;
\t}
\tmessage Member { optional uint32 account_id = 1; }
}
enum EStat { k_A = 0; k_B = 1; }
message CMsgNew { optional bool x = 1; }
'''


def test_protobuf_diff_reads_fields_by_message_not_by_line():
    rows = protobuf_diff.diff_file('common.proto', PROTO_OLD, PROTO_NEW)
    got = {(r['scope'], r['op'], r.get('item')) for r in rows}
    assert got == {('CMsgNew', 'added', None),
                   ('CSOCitadelParty', 'removed', 'is_high_skill_range_party'),
                   ('CSOCitadelParty', 'changed', 'solo'),        # a oneof's field belongs to its message
                   ('EStat', 'added', 'k_B')}                     # re-spaced party_id is no change


def test_strings_keep_text_and_spell_out_type_names():
    assert strings_diff.clean('.?AV?$CModifierFactory@VCCitadel_Modifier_Nurse_Fear_Debuff@@$0PPPP@@@') == \
        'CModifierFactory<CCitadel_Modifier_Nurse_Fear_Debuff>'
    assert strings_diff.clean('?citadel_local_player_ranked_badge_prop') == 'citadel_local_player_ranked_badge_prop'
    for junk in (';<}\\v<}\\vC_TonemapController2', '0TAB', 'Oct 20 2026', '6666666666666666HeroPersona_t'):
        assert strings_diff.clean(junk) is None, junk
    d = strings_diff.diff_text('IsHighSkillRange\nKeepMe_String\nOct 16 2026', 'KeepMe_String\nOct 20 2026')
    assert d == {'added': [], 'removed': ['IsHighSkillRange'], 'n_added': 0, 'n_removed': 1}


def test_files_go_to_their_hero_and_a_graph_shared_by_all_is_one_row():
    owners = extras.model_owners('\thero_nurse =\n\t\tm_strModelName = resource_name:"models/heroes_wip/nurse/nurse.vmdl"\n'
                                 '\thero_ghost =\n')
    ops = {'models/heroes_wip/nurse/nurse.vmdl_c': 'modified',
           'models/heroes_wip/nurse/anims/run.vanim_c': 'added',
           'particles/abilities/nurse/fear.vpcf_c': 'added',
           'sounds/vo/ghost/hello.vsnd_c': 'added',
           'materials/particle/projected/x.vmat_c': 'modified'}           # no owner: counts only
    ops.update({f'animgraphs/animgraph2/hero/hero_leans.vnmgraph+h{i}.vnmgraph_c': 'modified'
                for i in range(extras.SHARED_GRAPH)})
    got = extras.asset_owners(ops, owners)
    assert got == {'*': {'graph hero_leans': [0, 0, extras.SHARED_GRAPH]},
                   'hero_ghost': {'voice': [1, 0, 0]},
                   'hero_nurse': {'animation': [1, 0, 0], 'model': [0, 0, 1], 'particles': [1, 0, 0]}}


def test_dll_summary_merges_two_steam_builds_and_spells_names():
    rows = [{'build': '6815', 'dlls': {'server': {'changed': 2, 'added': 1, 'removed': 0, 'unnamed': 1,
                                                  'functions': [{'name': 'Radius', 'weight': 5}]}},
             'other_dlls_changed': ['engine2']},
            {'build': '6815', 'dlls': {'server': {'changed': 1, 'added': 0, 'removed': 0, 'unnamed': 0,
                                                  'functions': [{'name': 'Radius', 'weight': 9},
                                                                {'name': '.?AVCFoo@@', 'weight': 1}]}},
             'other_dlls_changed': ['particles']},
            {'build': 'unknown', 'dlls': {}}]
    out = ids.convert(rows)
    assert list(out) == ['6815']
    s = out['6815']['dlls']['server']
    assert (s['changed'], s['added'], s['unnamed']) == (3, 1, 1)
    assert s['functions'] == [{'name': 'Radius', 'weight': 9}, {'name': 'CFoo', 'weight': 1}]
    assert out['6815']['other'] == ['engine2', 'particles']


def test_build_page_sections_show_the_change_and_no_noise(monkeypatch):
    monkeypatch.setattr(build_tech, 'names_by_id', lambda: {'hero_nurse': 'Nurse'})
    assets = {'counts': {'hero_model': {'added': 2, 'removed': 0, 'modified': 9}},
              'owners': {'*': {'graph hero_leans': [0, 0, 51]}, 'hero_nurse': {'animation': [2, 0, 9]}},
              'notable': {'hero_model': [['modified', 'models/heroes_wip/nurse/nurse.vmdl_c']]}}
    html = build_tech.files_section(assets, '../')
    assert 'Nurse</a>' in html and 'animation +2 ~9' in html and 'All heroes' in html
    assert 'nurse.vmdl_c' not in html                   # a hero's model path: counted under the hero, not listed
    proto = [{'file': 'citadel_gcmessages_common.proto', 'scope': 'CSOCitadelParty', 'op': 'removed',
              'item': 'is_high_skill_range_party', 'old': 'optional bool is_high_skill_range_party = 13'}]
    html = build_tech.protobuf_section(proto, 6810, 'abc')
    assert 'removed: <code>optional bool is_high_skill_range_party = 13</code>' in html and '#diff-' in html
    html = build_tech.strings_section({'client': {'added': [], 'removed': ['IsHighSkillRange'], 'n_added': 0,
                                                  'n_removed': 1}}, 6810, 'abc')
    assert 'client.dll</a></b>' in html and '+0 −1' in html and '<code>IsHighSkillRange</code></span><span class="vals">removed' in html
    monkeypatch.setattr(build_tech, 'dll_changes', lambda: {'6810': {'dlls': {'client': {
        'changed': 3, 'added': 1, 'removed': 1, 'unnamed': 2, 'functions': [{'name': 'IsHighSkillRange', 'weight': 4}]}},
        'other': ['particles']}})
    html = build_tech.dll_section(6810)
    assert '<b>client.dll</b></span><span class="vals">3 changed' in html and 'particles.dll' in html
    assert 'weight' not in html and '+1' not in html            # moved functions are not shown as new / removed
    assert build_tech.dll_section(1) == ''
