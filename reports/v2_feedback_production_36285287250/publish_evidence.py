"""Copy verified evidence and supplementary read-only comparisons to a new report."""
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

from collect import item, REPO
sys.path.insert(0, str(REPO))
from experiments.v2_feedback_production.run import git_blob, ARMS, SEEDS, MODES
from experiments.v2_online_feedback.prepare import write

ROOT = Path(__file__).parent
DATA = ROOT / 'completed_36285287250'
OUT = REPO / 'reports/v2_feedback_production_36285287250'
OUT.mkdir(parents=True, exist_ok=False)
for name in ('github_run.json', 'artifacts.json', 'jobs.json', 'gate_verified.json', 'readback_audit.json'):
    shutil.copyfile(DATA / name, OUT / name)
shutil.copytree(DATA / 'summary', OUT / 'summary')
shutil.copytree(DATA / 'display', OUT / 'display')
for name in ('PROTOCOL.md', 'RESUME.md'):
    shutil.copyfile(REPO / 'experiments/v2_feedback_production' / name, OUT / name)
shutil.copyfile(Path(__file__), OUT / 'publish_evidence.py')
shutil.copyfile(ROOT / 'collect.py', OUT / 'collect.py')
artifacts = json.loads((DATA / 'artifacts.json').read_text())['artifacts']
archives = {a['name']: DATA / 'original_artifacts' / f"{a['id']}.zip" for a in artifacts}
extra = {'initial_models_match_previous_report': [], 'ab_final_games_equal': [], 'ab_game_histories_equal': [],
         'final_goal_changed_seeds': {}, 'initial_game_feedback': []}
for seed in SEEDS:
    with zipfile.ZipFile(archives[f'production-world-{seed}-36285287250']) as z:
        expected = json.loads(git_blob(f'reports/v2_online_feedback_36281122365/registered_inputs/{seed}/learner.json'))
        for arm in ARMS:
            for mode in MODES:
                prefix = f'{arm}_{mode}/'
                assert item(z, prefix+'evaluations/evaluation_000/initial_learner.json') == expected
                extra['initial_models_match_previous_report'].append([seed, arm, mode])
                result = item(z, prefix+'series.json')
                if result['final_goal_changed']:
                    extra['final_goal_changed_seeds'].setdefault(arm+'_'+mode, []).append(seed)
                stats = item(z, prefix+'evaluations/evaluation_000/feedback_metrics.json')
                extra['initial_game_feedback'].append({'seed': seed, 'arm': arm, 'mode': mode,
                    'first_goal_observation_step': stats['first_goal_observation_step'],
                    'initial_game_successes_after_feedback': result['initial_metrics']['successes']})
        for mode in MODES:
            a = item(z, f'{ARMS[0]}_{mode}/history.json')
            b = item(z, f'{ARMS[1]}_{mode}/history.json')
            same = a[-1]['game'] == b[-1]['game']
            extra['ab_final_games_equal'].append({'seed': seed, 'mode': mode, 'equal': same})
            assert same
            project = lambda h: [{k: row.get(k) for k in ('game', 'candidate_game', 'accepted', 'critique', 'mutation')} for row in h]
            extra['ab_game_histories_equal'].append({'seed': seed, 'mode': mode, 'equal': project(a) == project(b)})
with zipfile.ZipFile(archives['production-gate-records-36285287250']) as z:
    name = next(n for n in z.namelist() if n.endswith('production-tests.xml'))
    xml = z.read(name)
    (OUT / 'tests.xml').write_bytes(xml)
    suites = list(ET.fromstring(xml).iter('testsuite'))
    extra['tests'] = {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
old = ROOT / 'attempt1/extracted/reports/connection_gate'
counts = Counter()
for path in old.rglob('execution_audit.json'):
    counts.update(json.loads(path.read_text())['phase_actions'])
extra['original_gate_phase_actions'] = dict(counts)
extra['original_gate_environment_actions'] = sum(counts.values())
extra['original_gate_resources'] = json.loads((old / 'resources.json').read_text())
extra['original_gate_incomplete_status_reason'] = 'All 26 evaluations completed; comparator erroneously included policy_seconds. Verification-only resume, no policy reruns.'
write(OUT / 'supplementary_readback.json', extra)
write(OUT / 'archive_locations.json', {
    'main_raw_archive_directory': str(DATA / 'original_artifacts'),
    'gate_raw_archive_directory': str(ROOT / 'attempt1/original_artifacts'),
    'github_artifact_retention_days': 90,
    'main_run': 36285287250, 'original_gate_run': 36284251256,
    'previous_comparison_preserved_at_commit': '90a7bba04ce8895869b6b2eb7b3dd7d8cae25207',
    'raw_files_remain_in_digest_verified_original_zip_archives': True})
print(json.dumps(extra, indent=2))
