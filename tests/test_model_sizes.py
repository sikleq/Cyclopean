"""A hero model whose file size moved several times over is a row of the hero's history (Doorman's luggage trolley,
build 6815: 1.68 MB -> 0.17 MB, a cart drawn twice; owner 2026-10-23)."""
from builders import history_view
from builders.model_rows import MODEL_PREFIX, model_name, model_rows
from pipeline import extras

TROLLEY = 'models/heroes_wip/doorman/doorman_luggagetrolley.vmdl_c'
TROLLEY_F = 'models/heroes_wip/doorman/doorman_luggagetrolley_friendly.vmdl_c'


def test_size_jump_found_only_for_hero_models_moved_several_times():
    removed = {TROLLEY: ('a', 1676401), 'models/heroes_wip/doorman/doorman.vmdl_c': ('b', 1000),
               'models/props/crate.vmdl_c': ('c', 1000), 'models/heroes_wip/doorman/x.vmat_c': ('d', 1000)}
    added = {TROLLEY: ('e', 167501), 'models/heroes_wip/doorman/doorman.vmdl_c': ('f', 2000),
             'models/props/crate.vmdl_c': ('g', 9000), 'models/heroes_wip/doorman/x.vmat_c': ('h', 9000)}
    assert extras.size_jumps(added, removed) == [{'path': TROLLEY, 'old': 1676401, 'new': 167501}]


def test_notable_files_capped_in_path_order(monkeypatch):
    paths = [f'models/npc/m{i:03d}/m.vmdl_c' for i in range(extras.NOTABLE_LIMIT + 20)]
    changes = ({p: ('a', 1) for p in reversed(paths)}, {p: ('b', 1) for p in paths})
    monkeypatch.setattr(extras, '_asset_changes', lambda prev, cur: changes)
    monkeypatch.setattr(extras, 'hero_owners', lambda commit: {})        # CI has no tracker clone
    out = extras.asset_diff('p', 'c')
    assert [x[1] for x in out['notable']['npc_model']] == paths[:extras.NOTABLE_LIMIT]


def test_model_folder_maps_to_its_hero_through_a_redo_folder():
    vdata = ('\thero_base = \n\t{\n\t\tm_strModelName = resource_name:"models/heroes_wip/gen_man/gen_man.vmdl"\n\t}\n'
             '\thero_doorman = \n\t{\n'
             '\t\tm_strModelName = resource_name:"models/heroes_wip/doorman_v2/doorman.vmdl"\n\t}\n')
    owners = extras.model_owners(vdata)
    assert owners['doorman'] == 'hero_doorman'
    assert owners['gen_man'] == 'hero_base'


def test_row_names_the_model_sizes_and_ratio_once_per_team_copy():
    html = model_rows([{'path': TROLLEY, 'old': 1676401, 'new': 167501},
                       {'path': TROLLEY_F, 'old': 1676457, 'new': 167525}])
    assert html.count('model-row') == 1
    assert 'luggagetrolley' in html and 'doorman_' not in html
    assert '1.68 MB' in html and '168 KB' in html and '10× smaller' in html
    assert 'is-hidden' in html


def test_model_that_came_back_inside_one_patch_has_no_row():
    piece = 'models/heroes_wip/necro/torso_piece05.vmdl_c'
    assert model_rows([{'path': piece, 'old': 34855, 'new': 2193, 'build': 6155},
                       {'path': piece, 'old': 2193, 'new': 34855, 'build': 6161}]) == ''


def test_model_name_drops_hero_folder_and_team_suffix():
    assert model_name(TROLLEY_F) == 'luggagetrolley'


def test_hero_history_shows_model_row_in_its_patch():
    key = 'heroes.vdata:hero_doorman'
    row = {'id': '2026-10-22', 'date': '2026-10-22', 'title': '10-22-2026 Update'}
    by_ent = {MODEL_PREFIX + key: [(row, [{'path': TROLLEY, 'old': 1676401, 'new': 167501, 'build': 6815}])]}
    html = history_view.history_table([(key, 'Doorman', None)], ['Doorman'], by_ent, {}, '../')
    assert 'No recorded changes' not in html
    assert 'luggagetrolley' in html and '10× smaller' in html
