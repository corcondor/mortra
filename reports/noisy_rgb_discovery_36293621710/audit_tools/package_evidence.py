"""Package existing evidence and display recorded pixels; no learning or rendering."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL

BASE = Path(__file__).parent/'completed'
REPO = Path('C:/Users/81808/.openclaw/workspace/mortra-v2-online-feedback-20260928')
OUT = REPO/'reports/noisy_rgb_discovery_36293621710'


def write(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)


def get(z, suffix):
    names = [n for n in z.namelist() if n.endswith(suffix)]
    assert len(names) == 1
    return z.read(names[0])


def read_frames(z, histories):
    qbytes = get(z, '/training/queries.jsonl.gz')
    queries = [json.loads(x) for x in gzip.decompress(qbytes).splitlines()]
    name = next(n for n in z.namelist() if n.endswith('/training/raw.rgb.gz'))
    selected = {}
    with z.open(name) as raw, gzip.GzipFile(fileobj=raw) as stream:
        for query in queries:
            size = int(np.prod(query['shape']))
            data = stream.read(size)
            word = tuple(query['history'])
            if word in histories and query['replicate'] == 0:
                batch = np.frombuffer(data, dtype=np.uint8).reshape(query['shape'])
                selected[word] = dict(query=query, rgb=batch[0].copy())
            if len(selected) == len(histories):
                break
    assert set(selected) == set(histories)
    return selected


def strip(rgb, scale=8):
    assert rgb.shape == (4, 12, 12, 3)
    image = Image.fromarray(np.concatenate(list(rgb), axis=1))
    return image.resize((48*scale, 12*scale), Image.Resampling.NEAREST)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    for name in ('github_run.json', 'artifacts.json', 'jobs.json', 'verified_results.json',
                 'closure_diagnosis.json', 'table_replay.json'):
        shutil.copyfile(BASE/name, OUT/name)
    shutil.copytree(BASE/'extracted', OUT/'condition_records')
    for file in BASE.glob('closure_additions_*.json'):
        shutil.copyfile(file, OUT/file.name)
    shutil.copyfile(REPO/'experiments/noisy_rgb_discovery/PROTOCOL.md', OUT/'PROTOCOL.md')
    shutil.copyfile(Path(__file__).parent/'README.md', OUT/'README.md')
    audit = OUT/'audit_tools'
    audit.mkdir()
    for name in ('collect.py', 'diagnose.py', 'replay_table.py', 'package_evidence.py'):
        shutil.copyfile(Path(__file__).parent/name, audit/name)
    artifacts = json.loads((BASE/'artifacts.json').read_text())['artifacts']
    verified = json.loads((BASE/'verified_results.json').read_text())
    diagnoses = json.loads((BASE/'closure_diagnosis.json').read_text())
    replays = json.loads((BASE/'table_replay.json').read_text())
    assert len(verified) == len(diagnoses) == len(replays) == 4
    assert all(r['status'] == 'PASS' for r in replays)
    tests = list((OUT/'condition_records').rglob('tests.xml'))
    assert len(tests) == 1
    xml = ET.parse(tests[0]).getroot()
    suites = list(xml.iter('testsuite'))
    assert sum(int(x.attrib['tests']) for x in suites) == 10
    assert sum(int(x.attrib['failures'])+int(x.attrib['errors']) for x in suites) == 0
    hashes = set()
    duplicate = exposures = actions = 0
    rows = []
    source_checks = []
    commit = '7ad519c5dbc3b7443b8f0549262246c1eb2296c5'
    git_hashes = {}
    frame_manifest = []
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 13)
    image = Image.new('RGB', (900, 680), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((18, 12), 'Recorded RGB inputs | run 36293621710 | no re-rendering', fill='black', font=font)
    draw.text((18, 40), 'Empty action history, exposure 0; four 12x12 views enlarged 8x.', fill='black', font=small)
    witnesses = Image.new('RGB', (1110, 850), 'white')
    wd = ImageDraw.Draw(witnesses)
    wd.text((18, 10), 'Recorded non-transitivity witnesses | first exposure, not the batch mean', fill='black', font=font)
    wd.text((18, 36), 'Distances below use all 8 exposures. Pictures show view 0 enlarged 10x.', fill='black', font=small)
    for i, verified_row in enumerate(sorted(verified, key=lambda x: (x['result']['seed'],x['result']['camera']))):
        result = verified_row['result']
        seed, camera = result['seed'], result['camera']
        diagnosis = next(d for d in diagnoses if d['seed'] == seed and d['camera'] == camera)
        artifact = next(a for a in artifacts if a['name'] == verified_row['artifact'])
        archive_path = BASE/'original_artifacts'/f"{artifact['id']}.zip"
        with zipfile.ZipFile(archive_path) as z:
            source = json.loads(get(z, '/source_snapshot.json'))
            assert source['commit'] == commit
            checks = {}
            for name, expected in source['files'].items():
                canonical = name.replace('\\', '/')
                if canonical not in git_hashes:
                    blob = subprocess.check_output(['git','show',f'{commit}:experiments/noisy_rgb_discovery/{canonical}'],cwd=REPO)
                    git_hashes[canonical] = dict(exact=hashlib.sha256(blob).hexdigest(),
                        checkout_crlf=hashlib.sha256(blob.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')).hexdigest())
                variants = git_hashes[canonical]
                if canonical.startswith('reference/'):
                    assert expected == variants['exact'], canonical
                else:
                    assert expected in variants.values(), canonical
                checks[canonical] = dict(recorded_sha256=expected,
                    matched='exact' if expected == variants['exact'] else 'checkout_crlf')
            source_checks.append(dict(seed=seed,camera=camera,commit=commit,files=checks))
            partial = json.loads(get(z, '/partial_table.json'))
            assert partial['E'] == [[]] and partial['events'] == []
            witness = diagnosis['nontransitivity_witness']
            histories = {()}
            if witness:
                histories.update(tuple(witness[k]) for k in ('a','bridge','b'))
            frames = read_frames(z, histories)
            first = frames[()]
            y = 78 + i*146
            draw.text((18,y), f'{seed} / {camera} / training / empty history', fill='black', font=font)
            image.paste(strip(first['rgb']), (18,y+26))
            draw.text((425,y+42), 'Stored input, not gameplay replay', fill='black', font=small)
            draw.text((425,y+64), f"Training query {first['query']['query']}, exposure 0", fill='black', font=small)
            frame_manifest.append(dict(seed=seed,camera=camera,kind='recorded_raw', history=[],
                                       query=first['query']['query'],exposure=0,sha256=first['query']['raw_hashes'][0]))
            if witness:
                wy = 76+i*185
                wd.text((18,wy), f'{seed} / {camera}', fill='black', font=font)
                for j, key in enumerate(('a','bridge','b')):
                    word = tuple(witness[key])
                    frame = frames[word]
                    pic = Image.fromarray(frame['rgb'][0]).resize((120,120),Image.Resampling.NEAREST)
                    witnesses.paste(pic,(18+j*146,wy+27))
                    wd.text((20+j*146,wy+151), key, fill='black',font=small)
                    frame_manifest.append(dict(seed=seed,camera=camera,kind='recorded_raw_witness',
                        label=key,history=word,query=frame['query']['query'],exposure=0,
                        sha256=frame['query']['raw_hashes'][0],displayed_view=0))
                wd.text((470,wy+38), f"threshold {witness['threshold']:.6f}", fill='black',font=font)
                wd.text((470,wy+68), f"z(a,bridge)={witness['z_a_bridge']:.6f}; z(bridge,b)={witness['z_bridge_b']:.6f}", fill='black',font=font)
                wd.text((470,wy+98), f"z(a,b)={witness['z_a_b']:.6f} > threshold", fill='black',font=font)
            for phase in ('calibration','training'):
                qbytes = get(z, f'/{phase}/queries.jsonl.gz')
                for line in gzip.decompress(qbytes).splitlines():
                    q = json.loads(line)
                    actions += len(q['history'])
                    for h in q['raw_hashes']:
                        duplicate += h in hashes
                        hashes.add(h)
                        exposures += 1
        rows.append(dict(seed=seed,camera=camera,status=result['status'],
             access_histories=diagnosis['access_histories'], provisional_groups=diagnosis['final_provisional_groups'],
             discovered_nonempty_suffixes=0,heldout_evaluated=0,closure_limit=1000,
             added_without_group=diagnosis['addition_reasons'].get('no_matching_group',0),
             added_ambiguous=diagnosis['addition_reasons'].get('multiple_matching_groups',0),
             wall_seconds=result['wall_seconds'],cpu_seconds=result['cpu_seconds'],
             peak_memory_bytes=result['peak_memory_bytes'],
             acquisition_actions=sum(s['environment_actions'] for s in result['acquisition_sensors']),
             exposure_sets=sum(s['exposures'] for s in result['acquisition_sensors'])))
    image.save(OUT/'recorded_rgb_inputs.png')
    witnesses.save(OUT/'recorded_rgb_nontransitivity.png')
    write(OUT/'image_provenance.json',frame_manifest)
    write(OUT/'executed_source_verification.json',source_checks)
    write(OUT/'aggregate.json',dict(status='INCOMPLETE',conditions=rows,unit_tests_passed=10,
         completed_models=0,heldout_evaluated=0,heldout_planned=20000,heldout_accuracy=None,
         total_environment_actions=actions,exposure_sets=exposures,views_per_exposure=4,
         exact_duplicate_exposure_sets_across_all_conditions=duplicate,
         experiment_source_commit='7ad519c5dbc3b7443b8f0549262246c1eb2296c5',
         global_exposure_hashes_previously_verified_from_raw=True,
         posthoc_audit_environment_actions=0))
    with (OUT/'conditions.csv').open('x',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    logs = subprocess.check_output(['gh','api','repos/corcondor/mortra/actions/runs/36293621710/logs'])
    with (OUT/'github_run_logs.zip').open('xb') as stream:
        stream.write(logs)
    write(OUT/'audit_runtime.json',dict(python=sys.version,numpy=np.__version__,pillow=PIL.__version__,
                                      platform=platform.platform()))
    registry = []
    for a in artifacts:
        archive_path = BASE/'original_artifacts'/f"{a['id']}.zip"
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        assert a['digest'] == 'sha256:'+digest
        registry.append(dict(id=a['id'],name=a['name'],sha256=digest,local_archive=str(archive_path),
            url=f"https://github.com/corcondor/mortra/actions/runs/36293621710/artifacts/{a['id']}",
            expires_at=a['expires_at']))
    write(OUT/'original_artifact_registry.json',registry)
    write(OUT/'packaged_file_hashes.json',{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in OUT.rglob('*') if p.is_file()})
    print(json.dumps(rows,indent=2),flush=True)
    print('Evidence preserved at '+str(OUT),flush=True)


if __name__ == '__main__':
    main()
