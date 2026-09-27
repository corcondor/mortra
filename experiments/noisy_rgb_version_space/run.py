import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np
import PIL
from PIL import Image, ImageDraw
import psutil

from experiments.noisy_rgb_discovery.core import calibrate, learner, model_record
from experiments.noisy_rgb_discovery.run import CONFIG as OLD_CONFIG, save_statistics, write
from experiments.noisy_rgb_discovery.sensor import Sensor, make_game
from experiments.noisy_rgb_discovery.source import EXPECTED, ROOT as REFERENCE_ROOT
from .core import CandidateLearner, Evidence
from .runtime import Budget, LIMITS, ResourceLimit, measured_statistics, stage_sensors

ROOT = Path(__file__).parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def old_match(output, seed, camera, statistics, table, result, calibration):
    directory = Path('reports/noisy_rgb_discovery_36293621710/condition_records')
    source = next(directory.glob(f'noisy-rgb-{seed}-{camera}-*/noisy_rgb_{seed}_{camera}'))
    saved = json.loads((source/'partial_table.json').read_text())
    checks = dict(S=json.loads(json.dumps(table.S)) == saved['S'],
                  E=json.loads(json.dumps(table.E)) == saved['E'],
                  statistics_keys=json.loads(json.dumps(list(statistics.cache))) == json.loads((source/'statistics_index.json').read_text()),
                  calibration=json.loads(json.dumps(calibration)) == json.loads((source/'calibration.json').read_text()))
    with gzip.open(source/'training/queries.jsonl.gz', 'rt') as a, gzip.open(output/'training/queries.jsonl.gz', 'rt') as b:
        checks['all_query_metadata_and_raw_hashes'] = [json.loads(s) for s in a] == [json.loads(s) for s in b]
    checks['status'] = result['status'] == 'RUN_NOT_COMPLETED_OLD_CLOSURE_LIMIT'
    record = dict(passed=all(checks.values()), checks=checks, reference_run=36293621710)
    write(output/'old_reproduction.json', record)
    return record


def save_input_image(sensor, output, seed, camera, arm):
    if sensor.first_sample is None:
        return
    pixels = np.concatenate(sensor.first_sample[0], axis=1)
    image = Image.fromarray(pixels).resize((576, 144), Image.Resampling.NEAREST)
    canvas = Image.new('RGB', (576, 186), 'white')
    canvas.paste(image, (0, 42))
    ImageDraw.Draw(canvas).text((5, 5), f'Saved input RGB | {seed} {camera} {arm}\n{sensor.namespace}, first query, exposure 0', fill='black')
    canvas.save(output/'recorded_input.png')
    write(output/'recorded_input_provenance.json', dict(seed=seed, camera=camera, arm=arm,
        namespace=sensor.namespace, query=0, exposure=0, source='raw.rgb.gz; not a reconstructed play',
        original_shape=list(sensor.first_sample[0].shape), raw_sha256=hashlib.sha256(sensor.first_sample[0].tobytes()).hexdigest(),
        run_id=os.getenv('GITHUB_RUN_ID')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['development', 'fresh'], required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--camera', choices=['base', 'shifted'], required=True)
    parser.add_argument('--arm', choices=['H', 'V'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.phase == 'development':
        assert args.seed in (95027004, 95027005)
    else:
        manifest = json.loads((ROOT/'fresh_manifest.json').read_text())
        assert manifest['development_gate_passed'] and args.seed in manifest['seeds']
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    config = dict(OLD_CONFIG, phase=args.phase, seed=args.seed, arm=args.arm, camera=args.camera,
                  new_limits=LIMITS, old_algorithm_unchanged=True, protocol_sha=sha(ROOT/'PROTOCOL_VS.md'))
    write(out/'config.json', config)
    files = {str(p): sha(p) for folder in (ROOT, ROOT.parent/'noisy_rgb_discovery')
             for p in folder.rglob('*') if p.is_file() and p.suffix in ('.py', '.md', '.json')}
    files['scripts/evaluate_autonomous_game_design_loop.py'] = sha(Path('scripts/evaluate_autonomous_game_design_loop.py'))
    for name, expected in EXPECTED.items():
        assert sha(REFERENCE_ROOT/name) == expected
    write(out/'source_snapshot.json', dict(files=files, commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        command=sys.argv, python=sys.version, numpy=np.__version__, pillow=PIL.__version__, platform=platform.platform(),
        run_id=os.getenv('GITHUB_RUN_ID'), attempt=os.getenv('GITHUB_RUN_ATTEMPT'), thread_env={
        k: os.getenv(k) for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}))
    started, cpu = time.perf_counter(), time.process_time()
    budget = Budget(**LIMITS) if args.arm == 'V' else None
    sensors, stats, table, model = {}, {}, None, None
    event_counts = Counter()
    result = dict(status='NOT_STARTED', phase=args.phase, seed=args.seed, camera=args.camera, arm=args.arm,
                  heldout=None, model_audit=None, control=None)
    events = gzip.open(out/'events.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1)
    log = (out/'run.log').open('x', encoding='utf-8', buffering=1)
    def emit(row):
        event_counts[row['event']] += 1
        r = dict(row, elapsed_seconds=time.perf_counter()-started)
        events.write(json.dumps(r)+'\n')
        if row['event'] in ('calibrated', 'state_added', 'suffix_added', 'resource_limit', 'acquisition_frozen') or (
                row['event'] == 'access_added' and row['access_count'] % 100 == 0):
            text = json.dumps(r)
            log.write(text+'\n')
            print(text, flush=True)
    bias = OLD_CONFIG['cameras'][args.camera]
    game = make_game(args.seed)
    try:
        cal = Sensor(game, bias, 'calibration-v1', out/'calibration', 8, 12)
        sensors['calibration'] = cal
        calibration = measured_statistics(cal, budget)
        threshold, calibration_record = calibrate(calibration, cal.port.actions)
        write(out/'calibration.json', calibration_record)
        emit(dict(event='calibrated', threshold=threshold))
        if args.arm == 'H':
            sensor = Sensor(game, bias, 'training-v1', out/'training', 8, 12)
            sensors[8], stats[8] = sensor, measured_statistics(sensor)
            table = learner(stats[8], sensor.port.actions, threshold, emit)
            try:
                model, rounds = table.learn(max_rounds=20, depth=2)
                write(out/'rounds.json', rounds)
                result['status'] = 'INCOMPLETE_OLD_ROUND_LIMIT' if rounds[-1]['counterexample'] else 'COMPLETED_BOUNDED_EMPIRICAL_TEST'
            except RuntimeError as error:
                if str(error) != 'table did not stabilize':
                    raise
                result['status'] = 'RUN_NOT_COMPLETED_OLD_CLOSURE_LIMIT'
                result['resource_reason'] = 'original_1000_closure_passes'
        else:
            training, stats = stage_sensors(game, bias, out, 'training', budget)
            sensors.update(training)
            evidence = Evidence(stats, threshold, args.camera, emit, budget.check)
            table = CandidateLearner(evidence, training[8].port.actions, emit, budget.check)
            model, result['status'] = table.learn()
        if model is not None and result['status'].startswith('COMPLETED'):
            from .evaluate import prototypes_for
            prototypes = prototypes_for(model, list(table.E), stats, args.arm)
            write(out/'model.json', model_record(model, table.E))
    except ResourceLimit as error:
        result.update(status='INCOMPLETE_RESOURCE_LIMIT', resource_reason=str(error))
        emit(dict(event='resource_limit', resource=str(error)))
        model = None
    except Exception:
        result.update(status='IMPLEMENTATION_ERROR', traceback=traceback.format_exc())
        log.write(result['traceback'])
        model = None
    finally:
        result.update(acquisition_wall_seconds=time.perf_counter()-started, acquisition_cpu_seconds=time.process_time()-cpu)
        for sensor in sensors.values():
            sensor.close()
        if table is not None:
            write(out/'partial_table.json', dict(S=table.S, E=table.E, events=table.events))
            result.update(access_histories=len(table.S), suffixes=list(table.E), nonempty_suffix_count=len(table.E)-1)
            if args.arm == 'V':
                write(out/'unresolved_queue.json', list(table.queue.values()))
                result['mechanisms'] = dict(table.counts, **table.evidence.counts, remaining_unresolved=len(table.queue))
        for n, statistics in stats.items():
            directory = out/f'statistics_{n}'
            directory.mkdir()
            save_statistics(statistics, directory)
        if 8 in sensors:
            save_input_image(sensors[8], out, args.seed, args.camera, args.arm)
        result['acquisition_sensors'] = [dict(namespace=s.namespace, **s.metrics()) for s in sensors.values()]
        result['acquisition_environment_actions'] = sum(s.actions for s in sensors.values())
        result['acquisition_exposure_sets'] = sum(s.exposures for s in sensors.values())
        emit(dict(event='acquisition_frozen', status=result['status']))
        events.close()
    write(out/'acquisition_result.json', result)
    try:
        if args.arm == 'H' and args.phase == 'development' and table is not None:
            # The old index lives at the report root; compare in memory without
            # changing either output layout or the reference acquisition order.
            result['old_reproduction'] = old_match(out, args.seed, args.camera, stats[8], table, result, calibration_record)
        if args.arm == 'V' and table is not None:
            from .evaluate import acquisition_audit
            result['acquisition_audit'] = acquisition_audit(game, out/'events.jsonl.gz', table.S, out)
            write(out/'acquisition_audit.json', result['acquisition_audit'])
        if model is not None and result['status'].startswith('COMPLETED'):
            from .evaluate import heldout, control
            frozen = (sha(out/'model.json'), tuple(s.query_count for s in stats.values()),
                      None if args.arm == 'H' else table.evidence.version)
            result['model_audit'], result['heldout'] = heldout(game, bias, model, list(table.E), prototypes,
                                                              threshold, out, args.seed, args.arm)
            write(out/'model_audit.json', result['model_audit'])
            write(out/'heldout_summary.json', result['heldout'])
            if args.arm == 'V':
                result['control'] = control(args.seed, model, out)
            assert frozen == (sha(out/'model.json'), tuple(s.query_count for s in stats.values()),
                              None if args.arm == 'H' else table.evidence.version)
            result['unchanged_after_freeze'] = True
    except Exception:
        result['postfreeze_error'] = traceback.format_exc()
        log.write(result['postfreeze_error'])
    memory = psutil.Process().memory_info()
    result.update(event_counts=dict(event_counts), wall_seconds=time.perf_counter()-started,
                  cpu_seconds=time.process_time()-cpu, peak_memory_bytes=getattr(memory, 'peak_wset', memory.rss))
    write(out/'result.json', result)
    digest = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
    log.write(json.dumps(result)+'\n')
    log.close()
    digest['run.log'] = sha(out/'run.log')
    write(out/'artifact_hashes.json', digest)
    print(json.dumps(result), flush=True)
    if result['status'] == 'IMPLEMENTATION_ERROR' or 'postfreeze_error' in result:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
