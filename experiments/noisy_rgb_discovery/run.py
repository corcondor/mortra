import argparse
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

from .core import Statistics, calibrate, learner, model_record
from .sensor import Sensor, make_game
from .source import EXPECTED

ROOT = Path(__file__).parent
CONFIG = {
    'kind': 'KNOWN_SEED_DEVELOPMENT_NOISY_RGB_SUFFIX_DISCOVERY',
    'seeds': [95027004, 95027005],
    'cameras': {'base': [0., 0.], 'shifted': [.32, -.24]},
    'initial_suffixes': [[]], 'batch': 8, 'image_size': 12,
    'noise_floor': .01, 'calibration_histories': 100, 'calibration_margin': 1.18,
    'reference_max_rounds': 20, 'reference_conformance_depth': 2, 'reference_max_closure_passes': 1000,
    'heldout_episodes': 200, 'heldout_steps_per_episode': 25, 'heldout_action_seed_offset': 1000000,
    'camera_adaptation': 'separate learners; same fixed physics and RGB perturbation code',
    'learner_inputs': ['noisy four-view RGB', 'opaque executed action IDs'],
    'forbidden_inputs': ['success flag', 'clean RGB', 'true state IDs', 'reference access states', 'reference suffixes'],
    'stopping_claim': 'bounded empirical conformance only; no universal equality guarantee',
}


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def fingerprint(model, suffixes):
    return hashlib.sha256(json.dumps(model_record(model, suffixes), sort_keys=True).encode()).hexdigest()


def save_statistics(statistics, directory):
    keys = list(statistics.cache)
    write(directory / 'statistics_index.json', [[list(h), rep] for h, rep in keys])
    with gzip.open(directory / 'statistics.bin.gz', 'wb', compresslevel=1) as stream:
        for key in keys:
            s = statistics.cache[key]
            stream.write(np.stack([s.mean, s.var]).astype('<f4').tobytes())


def save_witnesses(statistics, events, output, size):
    for i, event in enumerate(events):
        words = [tuple(event['history1']), tuple(event['history2'])]
        suffix = tuple(event['suffix'])
        words += [w+suffix for w in words]
        width = 4*size*6
        canvas = Image.new('RGB', (width, 4*(size*6+24)), 'white')
        draw = ImageDraw.Draw(canvas)
        for row, word in enumerate(words):
            mean = statistics.cache[(word, 0)].mean.reshape(4, size, size, 3)
            array = np.concatenate(mean, axis=1)
            image = Image.fromarray(np.clip(np.rint(array*255), 0, 255).astype(np.uint8))
            image = image.resize((width, size*6), Image.Resampling.NEAREST)
            y = row*(size*6+24)
            draw.text((2, y+2), f"history {row % 2+1}, {'before' if row < 2 else 'after suffix '+str(suffix)}", fill='black')
            canvas.paste(image, (0, y+24))
        canvas.save(output / f'witness_{i:03d}_mean_of_8_exposures.png')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=CONFIG['seeds'], required=True)
    parser.add_argument('--camera', choices=CONFIG['cameras'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    write(out / 'config.json', dict(CONFIG, seed=args.seed, camera=args.camera))
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.py', '.md', '.json')}
    write(out / 'source_snapshot.json', dict(files=hashes, reference_expected=EXPECTED,
          commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          command=sys.argv, python=sys.version, numpy=np.__version__, pillow=PIL.__version__,
          platform=platform.platform(), run_id=os.getenv('GITHUB_RUN_ID')))
    log = (out / 'events.jsonl').open('x', encoding='utf-8', buffering=1)
    start, cpu = time.perf_counter(), time.process_time()
    sensors = []
    table = stats = None
    result = {'status': 'RUN_NOT_COMPLETED', 'seed': args.seed, 'camera': args.camera}

    def emit(row):
        row = dict(row, elapsed_seconds=time.perf_counter()-start)
        log.write(json.dumps(row)+'\n')
        if row['event'] != 'access_added' or row['access_count'] % 25 == 0:
            print(json.dumps(row), flush=True)

    try:
        game = make_game(args.seed)
        bias = CONFIG['cameras'][args.camera]
        cal_sensor = Sensor(game, bias, 'calibration-v1', out / 'calibration', CONFIG['batch'], CONFIG['image_size'])
        sensors.append(cal_sensor)
        calibration = Statistics(cal_sensor.port, CONFIG['noise_floor'])
        threshold, calibration_record = calibrate(calibration, cal_sensor.port.actions,
            CONFIG['calibration_histories'], CONFIG['calibration_margin'])
        write(out / 'calibration.json', calibration_record)
        emit(dict(event='calibrated', threshold=threshold, sensor=cal_sensor.metrics()))
        sensor = Sensor(game, bias, 'training-v1', out / 'training', CONFIG['batch'], CONFIG['image_size'])
        sensors.append(sensor)
        stats = Statistics(sensor.port, CONFIG['noise_floor'])
        table = learner(stats, sensor.port.actions, threshold, emit)
        assert table.E == [()] and table.S == [()]
        model, rounds = table.learn(max_rounds=CONFIG['reference_max_rounds'], depth=CONFIG['reference_conformance_depth'])
        for h in model['reps']:
            for e in table.E:
                stats.summary(tuple(h)+tuple(e))
        write(out / 'rounds.json', rounds)
        write(out / 'model.json', model_record(model, table.E))
        write(out / 'suffix_events.json', table.events)
        save_statistics(stats, out)
        save_witnesses(stats, table.events, out, CONFIG['image_size'])
        if rounds[-1]['counterexample']:
            result['status'] = 'INCOMPLETE_REFERENCE_ROUND_LIMIT'
        else:
            before = fingerprint(model, table.E)
            training_queries = stats.query_count
            emit(dict(event='learner_frozen', states=len(model['reps']), suffixes=list(table.E), model_hash=before))
            from .evaluate import heldout
            audit, metrics = heldout(game, bias, model, list(table.E), stats, threshold, out,
                                    args.seed, CONFIG['batch'], CONFIG['image_size'])
            assert before == fingerprint(model, table.E) and training_queries == stats.query_count
            write(out / 'model_audit.json', audit)
            write(out / 'heldout_summary.json', metrics)
            result.update(status='COMPLETED_BOUNDED_EMPIRICAL_TEST', model_audit=audit, heldout=metrics,
                          model_unchanged_during_evaluation=True)
        result.update(states=len(model['reps']), suffixes=list(table.E), suffix_events=len(table.events))
    except Exception as error:
        result.update(status='RUN_NOT_COMPLETED', error=repr(error), traceback=traceback.format_exc())
        if table is not None:
            write(out / 'partial_table.json', dict(S=list(table.S), E=list(table.E), events=table.events))
        if stats is not None and not (out / 'statistics_index.json').exists():
            save_statistics(stats, out)
        print(result['traceback'], flush=True)
    finally:
        for sensor in sensors:
            sensor.close()
        memory = psutil.Process().memory_info()
        result.update(wall_seconds=time.perf_counter()-start, cpu_seconds=time.process_time()-cpu,
                      peak_memory_bytes=getattr(memory, 'peak_wset', memory.rss),
                      acquisition_sensors=[dict(namespace=s.namespace, **s.metrics()) for s in sensors])
        write(out / 'result.json', result)
        log.close()
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
