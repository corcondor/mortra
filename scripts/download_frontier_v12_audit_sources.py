"""Read official immutable Actions artifacts, selecting the latest audit attempt."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

RUN='36107649938'
REPO='corcondor/mortra'


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--field-only',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    pages=subprocess.check_output(['gh','api',f'repos/{REPO}/actions/runs/{RUN}/artifacts?per_page=100'])
    artifacts=json.loads(pages)['artifacts'];latest={}
    for item in artifacts:
        name=item['name']
        if name in ('v12-frozen','v12-summary') or name.startswith('v12-holdout-') or (not a.field_only and name.startswith('v12-evolution-')):
            if name not in latest or item['created_at']>latest[name]['created_at']:latest[name]=item
    assert len(latest)==(10 if a.field_only else 18)
    for name,item in sorted(latest.items()):
        assert not item['expired']
        directory=a.output/('frozen' if name=='v12-frozen' else 'summary' if name=='v12-summary' else
            'holdout/'+name if name.startswith('v12-holdout-') else 'evolution/'+name)
        directory.mkdir(parents=True,exist_ok=False)
        with tempfile.TemporaryDirectory(prefix='artifact-',dir=a.output) as temp:
            assert Path(temp).resolve().parent==a.output.resolve()
            archive=Path(temp)/'source.zip'
            with archive.open('wb') as f:
                subprocess.run(['gh','api',f'repos/{REPO}/actions/artifacts/{item["id"]}/zip'],stdout=f,check=True)
            with zipfile.ZipFile(archive) as z:
                for member in z.namelist():
                    assert (directory/member).resolve().is_relative_to(directory.resolve())
                z.extractall(directory)
        print('DOWNLOADED',name,item['id'],flush=True)
    (a.output/'download_manifest.json').write_text(json.dumps(latest,indent=2),encoding='utf-8')


if __name__=='__main__':main()
