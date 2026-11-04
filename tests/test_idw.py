import numpy as np
import pytest
from shapely.geometry import Polygon
from imd_data import idw_surface


def test_idw_exact_samples_and_middle():
    x,y,z=idw_surface([75,76],[10,10],[10,20],(75,9.5,76,10.5),resolution=3)
    assert z[1,0]==10
    assert z[1,2]==20
    assert z[1,1]==pytest.approx(15)


def test_idw_masks_holes_and_exterior_and_ignores_missing():
    polygon=Polygon([(75,10),(77,10),(77,12),(75,12)],holes=[[(75.5,10.5),(76.5,10.5),(76.5,11.5),(75.5,11.5)]])
    x,y,z=idw_surface([75,77,76],[10,12,11],[20,20,np.nan],(74,9,78,13),geometry=polygon,resolution=9)
    assert np.isnan(z[4,4])
    assert np.isnan(z[0,0])
    assert z[2,2]==pytest.approx(20)
    assert np.nanmin(z)==pytest.approx(20)


def test_idw_all_missing_returns_empty_surface():
    x,y,z=idw_surface([75],[10],[np.nan],(74,9,76,11),resolution=10)
    assert np.isnan(z).all()


def test_idw_constant_and_invalid_settings():
    _,_,z=idw_surface([75],[10],[27],(74,9,76,11),resolution=10)
    assert np.allclose(z,27)
    with pytest.raises(ValueError):idw_surface([75],[10],[27],(74,9,76,11),power=0)
