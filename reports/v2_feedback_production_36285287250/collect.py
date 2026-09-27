"""Archive finished Actions evidence and render saved traces; no policy runs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

REPO = Path('C:/Users/81808/.openclaw/workspace/mortra-v2-online-feedback-20260928')
sys.path.insert(0, str(REPO))
from experiments.v2_online_feedback.prepare import download, write


def api(endpoint):
    return json.loads(subprocess.check_output(['gh', 'api', endpoint], text=True, encoding='utf-8'))


def item(archive, suffix):
    names = [n for n in archive.namelist() if n.endswith(suffix)]
    assert len(names) == 1, (suffix, names)
    return json.loads(archive.read(names[0]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    run = api(f'repos/corcondor/mortra/actions/runs/{a.run}')
    assert run['status'] == 'completed'
    artifacts = api(f'repos/corcondor/mortra/actions/runs/{a.run}/artifacts?per_page=100')
    write(a.output / 'github_run.json', run)
    write(a.output / 'artifacts.json', artifacts)
    write(a.output / 'jobs.json', api(f'repos/corcondor/mortra/actions/runs/{a.run}/jobs?per_page=100'))
    archives = {}
    for entry in artifacts['artifacts']:
        path = a.output / 'original_artifacts' / f"{entry['id']}.zip"
        download(entry, path)
        archives[entry['name']] = path
        print('verified', entry['name'], path.stat().st_size, flush=True)
    if run['conclusion'] != 'success':
        write(a.output / 'incomplete.json', {'status': 'INCOMPLETE', 'conclusion': run['conclusion']})
        return
    arms = ('frozen', 'record_and_replan', 'record_replan_and_explore')
    totals = Counter()
    checks = []
    image_cases = []
    for seed in range(79020000, 79020008):
        world_path = archives[f'production-world-{seed}-{a.run}']
        common_path = archives[f'production-common-{seed}-{a.run}']
        with zipfile.ZipFile(world_path) as world, zipfile.ZipFile(common_path) as common:
            completion = item(world, 'world_complete.json')
            assert len(completion['series']) == 6
            initial_models = []
            for arm in arms:
                for mode in ('targeted', 'random'):
                    prefix = f'{arm}_{mode}/'
                    history = item(world, prefix + 'history.json')
                    assert len(history) == 21
                    assert item(world, prefix + 'final_game.json') == history[-1]['game']
                    initial_models.append(item(world, prefix + 'evaluations/evaluation_000/initial_learner.json'))
                    for i in range(21):
                        audit = item(world, prefix + f'evaluations/evaluation_{i:03d}/execution_audit.json')
                        assert audit['phase_actions']['initial'] == 2500 and audit['phase_actions']['additional'] == 5000
                        assert audit['same_learner_before_after_feedback_and_frozen'] and audit['fresh_learner']
                        assert audit['no_random_or_evaluation_learning'] and audit['no_reset_edges']
                        assert audit['metrics'] == history[i].get('candidate_metrics', history[i]['metrics'])
                        totals.update(audit['phase_actions'])
                        totals['candidate_evaluations'] += 1
                    trials = item(common, prefix + 'evaluations/evaluation_000/frozen_trials.json')
                    game = item(world, prefix + 'final_game.json')
                    audit = item(common, prefix + 'evaluations/evaluation_000/execution_audit.json')
                    image_cases.append((seed, arm, mode, game, trials['mortra'][0]))
                    totals['common_environment_actions'] += audit['total_environment_actions']
                    totals['common_evaluations'] += 1
            assert all(m == initial_models[0] for m in initial_models)
            checks.append({'seed': seed, 'initial_2500_models_equal_in_all_six_series': True,
                           'candidate_evaluations_checked': 126, 'common_evaluations_checked': 6})
    assert totals['candidate_evaluations'] == 1008 and totals['common_evaluations'] == 48
    with zipfile.ZipFile(archives[f'production-summary-{a.run}']) as archive:
        for name in archive.namelist():
            path = a.output / 'summary' / Path(name).name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(archive.read(name))
    with zipfile.ZipFile(archives[f'production-gate-records-{a.run}']) as archive:
        gate = item(archive, 'gate_pass.json')
        assert gate['passed'] and gate['mocks_used'] is False
        write(a.output / 'gate_verified.json', gate)
    write(a.output / 'readback_audit.json', {'status': 'PASS', 'checks': checks, 'operation_totals': dict(totals)})
    render(image_cases, a.output / 'display', a.run)


def render(cases, directory, run):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    directory.mkdir()
    manifest = []
    for seed in range(79020000, 79020008):
        for mode in ('targeted', 'random'):
            chosen = [c for c in cases if c[0] == seed and c[2] == mode]
            fig, axes = plt.subplots(1, 3, figsize=(15, 5.4), constrained_layout=True)
            fig.suptitle(f'Run {run} | seed {seed} | {mode} | final games, common C evaluator\n'
                         'Recorded state/action projection, trial 0; not captured gameplay frames', fontsize=12)
            for ax, (_, arm, _, game, trial), label in zip(axes, chosen, ('A', 'B', 'C')):
                ax.set(xlim=(-.5, game['width']-.5), ylim=(game['height']-.5, -.5), aspect='equal')
                ax.set_xticks([]); ax.set_yticks([])
                for x, y in game['walls']:
                    ax.add_patch(Rectangle((x-.5, y-.5), 1, 1, color='#454b52'))
                for x, y in game['hazards']:
                    ax.plot(x, y, 'x', color='#d52f50')
                for field, letter in [('key_pos', 'K'), ('door_pos', 'D'), ('switch_pos', 'S'), ('gate_pos', 'G'),
                                      ('block_pos', 'B'), ('teleport_a', 'P'), ('teleport_b', 'P')]:
                    if game[field]:
                        ax.text(*game[field], letter, ha='center', va='center', color='#996000', fontsize=9)
                ax.plot(*game['start_pos'], 's', color='#337da6', label='start')
                ax.plot(*game['goal_pos'], '*', color='#e5a716', markersize=12, label='goal')
                states = trial['states']
                ax.plot([s[0] for s in states], [s[1] for s in states], color='#128877', linewidth=2)
                ax.plot(states[-1][0], states[-1][1], '.', color='black')
                ax.set_title(f"Designed under {label}\n{len(trial['actions'])} actions, success={trial['success']}", fontsize=11)
            axes[0].legend(loc='lower left', fontsize=8)
            path = directory / f'common_final_{seed}_{mode}.png'
            fig.savefig(path, dpi=150)
            plt.close(fig)
            manifest.append({'seed': seed, 'mode': mode, 'run': run, 'trial': 0, 'file': path.name,
                             'kind': 'saved_state_action_projection'})
    write(directory / 'manifest.json', manifest)


if __name__ == '__main__':
    main()
