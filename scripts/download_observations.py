"""Download the exact project inputs, verifying every byte against the manifest."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def download(entry,destination):
    path=destination/entry['file']
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']:
        return f"Verified {entry['file']}"
    file_id=re.search(r'/d/([^/]+)',entry['drive_url']).group(1)
    with urllib.request.urlopen('https://drive.google.com/uc?export=download&id='+file_id,timeout=120) as response:
        data=response.read()
    if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:
        raise ValueError(f"Integrity check failed: {entry['file']}; no file installed")
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.part');temporary.write_bytes(data);temporary.replace(path)
    return f"Downloaded {entry['file']}"

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,default=ROOT/'data/observations')
    parser.add_argument('--target',help='Optional manifest target ID')
    args=parser.parse_args()
    entries=json.loads((ROOT/'data/observation-manifest.json').read_text())
    if args.target: entries=[e for e in entries if e['target']==args.target]
    if not entries: parser.error('No matching target')
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(lambda entry:download(entry,args.destination),entries): print(result)
