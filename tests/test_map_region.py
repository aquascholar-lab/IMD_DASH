import pytest
from map_region import rectangle_bounds


def feature(coords):
    return {'type':'Feature','properties':{},'geometry':{'type':'Polygon','coordinates':[coords]}}


def test_drawn_rectangle_returns_geographic_bounds():
    f=feature([[76,11],[75,11],[75,10],[76,10],[76,11]])
    assert rectangle_bounds(f)==(75,10,76,11)


def test_reversed_draw_direction():
    f=feature([[75,10],[75,11],[76,11],[76,10],[75,10]])
    assert rectangle_bounds(f)==(75,10,76,11)


@pytest.mark.parametrize('coords',[
    [[75,10],[75,10],[75,10],[75,10],[75,10]],
    [[75,10],[76,11],[77,10],[76,9],[75,10]],
    [[179,10],[-179,10],[-179,11],[179,11],[179,10]],
    [[75,91],[76,91],[76,92],[75,92],[75,91]],
    [[75,10],[76,10],[76,11],[75,11]],
])
def test_invalid_rectangle_rejected(coords):
    with pytest.raises(ValueError):rectangle_bounds(feature(coords))


def test_empty_drawing_is_none():
    assert rectangle_bounds(None) is None
