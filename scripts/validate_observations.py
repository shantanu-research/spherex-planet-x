"""Produce a reproducible coverage and mode report; never invent scientific passes."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.real_pipeline import load, render, MODES
from backend.targets import resolve

names=[("Barnard's Star",'D1'),('WISE 0855-0714','D6'),('Epsilon Indi B','D3'),('RW Aur','D3'),('R Dra','D4')]
report={'description':'Coverage of supplied project FITS. Software success does not establish an astrophysical detection.','targets':[]}
for name,detector in names:
    target=resolve(name); exposures,_,_,errors,_=load(target,detector,6.5)
    entry={'target':name,'detector':detector,'usable_exposures':len(exposures),'visits':len({e.visit for e in exposures}),'input_errors':errors,'modes':{}}
    for mode in MODES:
        result=render(target,detector,6.5,mode)
        entry['modes'][mode]={'status':result['status'],'frames':len(result['frames']),'reason':result.get('message')}
    entry['photometry']=[e.photometry for e in exposures]
    report['targets'].append(entry)
    print(name,entry['usable_exposures'],entry['visits'],flush=True)
Path('docs/validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
