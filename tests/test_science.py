import numpy as np
import pytest
from backend.science import Exposure, balanced_stacks, resample, tracked, output_grid
from backend.targets import resolve

def exp(value,wave,visit,var=4):
    a=np.full((5,5),float(value))
    return Exposure(a,np.full_like(a,var),np.full_like(a,wave),np.full_like(a,.02),60000+visit*180,'D6','test.fits',(2,2),{},visit)

def test_balancing_equal_channels_preserves_variable_signal():
    # Duplicating one wavelength biases naive stacking but not a balanced stack.
    es=[exp(10,4.5,0),exp(10,4.5,0),exp(30,4.7,0),exp(15,4.5,1),exp(35,4.7,1)]
    result=balanced_stacks(es)
    np.testing.assert_allclose(result[0]['image'],20)
    np.testing.assert_allclose(result[1]['image'],25)
    np.testing.assert_allclose(result[0]['variance'],1.5)

def test_disjoint_wavelengths_are_not_temporal_comparisons():
    assert all(np.isnan(s['image']).all() for s in balanced_stacks([exp(10,4.5,0),exp(10,4.7,1)]))

def test_bilinear_variance_and_missing_pixels():
    im=np.ones((3,3)); var=np.full((3,3),4.)
    out,error=resample(im,var,np.array([[.5]]),np.array([[.5]]))
    assert out.item()==1 and error.item()==1
    im[0,0]=np.nan
    assert np.isnan(resample(im,var,np.array([[.5]]),np.array([[.5]]))[0]).all()

def test_tracking_moves_uncertainty_with_image():
    im=np.ones((5,5));var=np.full((5,5),4.);var[2,2]=16
    result=tracked({'image':im,'variance':var,'target_xy':(2,2)},(3,2))
    assert result['variance'][2,3]==16
    assert np.isnan(result['image'][:,0]).all()

def test_grid_has_north_up_east_left():
    grid,shape=output_grid(resolve('12,-20'),6.5)
    x,y=(shape[0]-1)/2,(shape[1]-1)/2
    ra,dec=grid.pixel_to_world_values(x,y)
    assert grid.pixel_to_world_values(x,y-1)[1]>dec
    assert grid.pixel_to_world_values(x-1,y)[0]>ra

@pytest.mark.parametrize('query',['360,0','12,91',''])
def test_invalid_coordinates(query):
    with pytest.raises(ValueError): resolve(query)

@pytest.mark.parametrize('mode',['visit_blink','longest_baseline','difference_sequence','motion_tracked','shift_stack','spectral_color','within_visit_fast','wavelength_matched'])
def test_real_renderer_modes_use_science_arrays(monkeypatch,mode):
    import json
    from backend import real_pipeline
    target=resolve('12,-20'); grid,shape=output_grid(target,1)
    exposures=[]
    for visit in range(3):
        for detector in ['D1','D3','D6']:
            e=exp(10+visit,4.5,visit);e.detector=detector
            e.image=np.full(shape,float(10+visit));e.variance=np.full(shape,4.)
            e.wavelength=np.full(shape,4.5);e.bandwidth=np.full(shape,.1)
            e.target_xy=((shape[0]-1)/2,)*2
            exposures.append(e)
    monkeypatch.setattr(real_pipeline,'load',lambda *args:(exposures,grid,shape,[],'test calibrated arrays'))
    result=real_pipeline.render(target,'D6',1,mode)
    assert result['status']=='success'
    assert len(result['frames'])==({'longest_baseline':2,'shift_stack':1,'wavelength_matched':2}.get(mode,3))
    assert result['flicker_audit'] is None
    json.dumps(result,allow_nan=False)
