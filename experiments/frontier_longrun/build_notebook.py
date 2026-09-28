"""Build a pinned, resumable Colab notebook; does not start an experiment."""
import argparse
import ast
import json
from pathlib import Path
import re


def notebook(sha):
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('exact commit required')
    intro = '''# MORTRA: long-run task-blind exploration

Run all cells. The existing MORTRA virtual_frontier is the primary explorer;
no external AI model is connected. Results and checkpoints are kept in Drive.
Run this same notebook again after a disconnect to continue saved work.

This is a new development experiment, not a restart of the noisy-RGB comparison.
It uses fully observed opaque state labels. Program worlds are 32x32; the 3D
controls remain the existing small arenas. Mining/building/crafting are NOT
implemented. The learner does not receive an oracle or the private world rules.

Maximum: 40 worlds x 3 methods x 131072 operations. Each notebook invocation
stops cleanly after about six hours or low available RAM. CPU only; no purchase,
automatic paid-resource upgrade, or Colab keep-alive is requested.
'''
    setup = f'''from google.colab import drive
drive.mount('/content/drive')
from pathlib import Path
import datetime, json, os, platform, subprocess, sys, uuid
SHA = {sha!r}
ROOT = Path('/content/drive/MyDrive/MORTRA/frontier-longrun-' + SHA[:12])
ROOT.mkdir(parents=True, exist_ok=True)
ATTEMPT = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
with (ROOT / ('runtime_' + ATTEMPT + '.json')).open('x') as f:
    json.dump({{'python': sys.version, 'platform': platform.platform(), 'cpus': os.cpu_count(),
               'meminfo': Path('/proc/meminfo').read_text(), 'source': SHA}}, f, indent=2)
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'uv'], check=True)
PY = '/content/mortra-frontier-env/bin/python'
if not Path(PY).exists():
    subprocess.run(['uv', 'venv', '--python', '3.12.10', '/content/mortra-frontier-env'], check=True)
subprocess.run(['uv','pip','install','--python',PY,'numpy==1.26.4','scipy==1.14.1',
                'pillow==11.3.0','psutil==7.0.0','pytest==8.3.5'], check=True)
REPO = Path('/content/mortra-frontier-' + SHA[:12])
if not REPO.exists():
    subprocess.run(['git','clone','--filter=blob:none','--no-checkout',
                    'https://github.com/corcondor/mortra.git',str(REPO)], check=True)
    subprocess.run(['git','sparse-checkout','set','experiments','scripts','tests'], cwd=REPO, check=True)
    subprocess.run(['git','checkout','--detach',SHA], cwd=REPO, check=True)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip() == SHA
assert not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=REPO,text=True).strip()
with (ROOT / ('pip_freeze_' + ATTEMPT + '.txt')).open('x') as f:
    subprocess.run(['uv','pip','freeze','--python',PY],stdout=f,check=True)
print('Runtime connected. Frozen source:', SHA)
print('Outputs:', ROOT)
'''
    tests = '''with (ROOT / ('tests_' + ATTEMPT + '.log')).open('x') as log:
    result = subprocess.run([PY,'-m','pytest','tests/test_frontier_longrun.py',
        'tests/test_virtual_frontier.py','-q',
        '--junitxml=' + str(ROOT / ('tests_' + ATTEMPT + '.xml'))],
        cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
print((ROOT / ('tests_' + ATTEMPT + '.log')).read_text())
assert result.returncode == 0, 'Validation failed; experiment NOT started'
'''
    run = '''with (ROOT / ('run_' + ATTEMPT + '.log')).open('x') as log:
    process = subprocess.Popen([PY,'-u','-m','experiments.frontier_longrun.runner',
        '--root',str(ROOT / 'results'),'--session-hours','6','--min-free-gib','1'],
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end='')
        log.write(line)
        log.flush()
    returncode = process.wait()
print('Exit code:', returncode)
print('Checkpoints remain saved in:', ROOT)
assert returncode == 0, 'Infrastructure or validation stop. Preserve logs; do not restart from zero.'
'''
    cells = [{'cell_type': 'markdown', 'metadata': {}, 'source': intro.splitlines(True)}]
    for source in (setup, tests, run):
        ast.parse(source)
        cells.append({'cell_type': 'code', 'metadata': {}, 'source': source.splitlines(True),
                      'execution_count': None, 'outputs': []})
    return {'nbformat': 4, 'nbformat_minor': 5, 'cells': cells,
            'metadata': {'kernelspec': {'display_name': 'Python 3', 'name': 'python3'},
                         'colab': {'name': 'MORTRA_frontier_longrun.ipynb'}}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(notebook(args.sha), stream, ensure_ascii=False, indent=2)
