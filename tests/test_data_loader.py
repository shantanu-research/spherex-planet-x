"""Integration checks against the optional, hash-pinned project FITS dataset."""
import json
from pathlib import Path
import pytest
from backend.real_pipeline import load, render, local_paths
from backend.targets import resolve

@pytest.mark.parametrize('name,detector', [("Barnard's Star",'D1'),('WISE 0855-0714','D6'),('Epsilon Indi B','D3'),('RW Aur','D3'),('R Dra','D4')])
def test_real_dataset(name,detector):
    target=resolve(name)
    if not local_paths(target): pytest.skip('Install project observations with scripts/download_observations.py')
    exposures,grid,shape,errors,source=load(target,detector,6.5)
    assert exposures
    result=render(target,detector,6.5,'within_visit_fast')
    assert result['status']=='success'
    assert result['is_real_data']
    assert all(f['source_file'].endswith('.fits') for f in result['frames'])
    assert result['flicker_audit'] is None
    assert not result['spectrophotometry']['detected_molecular_features']
    json.dumps(result,allow_nan=False)
