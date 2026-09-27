"""Read selected ZIP members with HTTP ranges; never download raw RGB archives."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path,PurePosixPath
import re
import urllib.error
import urllib.request
import zipfile

REPO='corcondor/mortra'
RUN=36309862254
EXECUTION='3e777cd5274a30e3119c125a932a6bbca98e1830'


def api(path):
    request=urllib.request.Request('https://api.github.com/'+path,headers={
        'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=120) as response:
        return json.load(response)


def completed_source():
    run=api(f'repos/{REPO}/actions/runs/{RUN}')
    assert run['head_sha']==EXECUTION
    assert run['status']=='completed', 'Source development must finish unchanged before audit'
    return {k:run[k] for k in ('id','head_sha','status','conclusion','html_url','updated_at')}


def artifact_list():
    rows=[]
    page=1
    while True:
        data=api(f'repos/{REPO}/actions/runs/{RUN}/artifacts?per_page=100&page={page}')
        rows.extend(data['artifacts'])
        if len(data['artifacts'])<100:
            return rows
        page+=1


def signed_location(artifact_id):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):
            return None
    request=urllib.request.Request(f'https://api.github.com/repos/{REPO}/actions/artifacts/{artifact_id}/zip',
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN']})
    try:
        urllib.request.build_opener(NoRedirect).open(request,timeout=120)
    except urllib.error.HTTPError as exc:
        if exc.code==302:
            return exc.headers['Location']
        raise
    raise RuntimeError('Expected archive redirect')


class HTTPRangeFile(io.RawIOBase):
    def __init__(self,url):
        self.url=url
        self.position=0
        self.bytes_read=0
        self.requests=0
        _,self.size=self.fetch(0,0)

    def fetch(self,start,end):
        request=urllib.request.Request(self.url,headers={'Range':f'bytes={start}-{end}'})
        with urllib.request.urlopen(request,timeout=120) as response:
            if response.status!=206:
                raise RuntimeError('Server did not honor Range; refuse entire archive transfer')
            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers['Content-Range'])
            assert match and (int(match[1]),int(match[2]))==(start,end)
            expected=end-start+1
            data=response.read(expected+1)
            assert len(data)==expected
        self.bytes_read+=len(data)
        self.requests+=1
        return data,int(match[3])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self,offset,whence=0):
        self.position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        if self.position<0:
            raise ValueError('Negative seek')
        return self.position

    def read(self,n=-1):
        n=min(self.size-self.position,n if n>=0 else self.size-self.position)
        if n<=0:
            return b''
        if n>64*1024*1024:
            raise RuntimeError('Refuse unexpectedly large single range')
        data,_=self.fetch(self.position,self.position+n-1)
        self.position+=len(data)
        return data


def wanted(name):
    parts=PurePosixPath(name).parts
    if '..' in parts or name.startswith('/') or ':' in name:
        return False
    root=next((i for i,p in enumerate(parts) if re.fullmatch(r'970270\d\d_(base|shifted)_V2',p)),None)
    if root is None:
        return False
    rel=parts[root+1:]
    if len(rel)==1:
        return rel[0] in {'result.json','acquisition_result.json','source_snapshot.json','config.json',
                          'calibration.json','artifact_hashes.json','events.jsonl.gz'}
    if rel and re.fullmatch(r'checkpoint_(50000|100000|250000|500000|final)',rel[0]):
        return rel[-1] in {'state.json','checkpoint.json','hashes.json','statistics_index.json'}
    return False


def extract_selected(archive,output):
    manifest={}
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            if not wanted(info.filename):
                continue
            parts=PurePosixPath(info.filename).parts
            root=next(i for i,p in enumerate(parts) if re.fullmatch(r'970270\d\d_(base|shifted)_V2',p))
            path=output.joinpath(*parts[root:])
            path.parent.mkdir(parents=True,exist_ok=True)
            digest=hashlib.sha256()
            with source.open(info) as stream,path.open('xb') as destination:
                while chunk:=stream.read(1024*1024):
                    destination.write(chunk); digest.update(chunk)
            manifest[str(path.relative_to(output)).replace('\\','/')]=dict(sha256=digest.hexdigest(),bytes=info.file_size,zip_crc=info.CRC)
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--camera',choices=['base','shifted'],required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    status=completed_source()
    name=(f'pv2-full-first-{RUN}' if (args.seed,args.camera)==(97027000,'base')
          else f'pv2-full-{args.seed}-{args.camera}-V2-{RUN}')
    matches=[a for a in artifact_list() if a['name']==name]
    assert len(matches)==1 and not matches[0]['expired'], ('Missing or expired source artifact',name)
    metadata=matches[0]
    args.output.mkdir(parents=True,exist_ok=False)
    reader=HTTPRangeFile(signed_location(metadata['id']))
    extracted=extract_selected(reader,args.output)
    assert extracted
    folder=args.output/f'{args.seed}_{args.camera}_V2'
    recorded=json.loads((folder/'artifact_hashes.json').read_text())
    recorded={k.replace('\\','/'):v for k,v in recorded.items()}
    for name,entry in extracted.items():
        relative=name.split('/',1)[1]
        if relative!='artifact_hashes.json':
            assert recorded[relative]==entry['sha256'], relative
    source=json.loads((folder/'source_snapshot.json').read_text())
    assert source['commit']==EXECUTION
    record=dict(upstream=status,artifact={k:metadata.get(k) for k in ('id','name','size_in_bytes','digest','expires_at')},
                range_bytes_read=reader.bytes_read,range_requests=reader.requests,members=extracted,
                all_selected_member_hashes_verified=True,full_archive_sha256_recomputed=False,
                integrity_scope='HTTPS + GitHub metadata digest retained; selected members checked against saved per-file SHA and ZIP CRC')
    (args.output/'download_manifest.json').write_text(json.dumps(record,indent=2))
    print(json.dumps({k:v for k,v in record.items() if k!='members'},indent=2))


if __name__=='__main__':
    main()
