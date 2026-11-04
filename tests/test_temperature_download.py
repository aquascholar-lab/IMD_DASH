import numpy as np
import pytest
from imd_data import download_temperature


class Response:
    def __init__(self,raw,url):
        self.content=raw
        self.url=url
        self.headers={'content-length':str(len(raw))}
    @property
    def text(self): return self.content.decode()
    def raise_for_status(self): pass
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def iter_content(self,*args): yield self.content


@pytest.mark.parametrize('product,landing', [('tmax','Max_1_Bin.html'),('tmin','Min_1_Bin.html')])
def test_temperature_download_discovers_form_and_preserves_hidden_fields(tmp_path,monkeypatch,product,landing):
    raw=np.full((366,31,31),25,dtype='<f4').tobytes()
    calls=[]
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,**kwargs):
            assert url.endswith(landing)
            return Response(b'<form action="annual.php" method="post"><input type="hidden" name="csrf" value="test"><select name="chosen_year"><option value="annual-2032">2032</option></select><input type="submit" name="fetch" value="Download"></form>',url)
        def request(self,method,url,**kwargs):
            calls.append((method,url,kwargs))
            return Response(raw,url)
    monkeypatch.setattr('imd_data.requests.Session',Session)
    path=download_temperature(2032,product,tmp_path)
    assert path.read_bytes()==raw
    assert calls[0][0]=='POST'
    assert calls[0][1]=='https://www.imdpune.gov.in/cmpg/Griddata/annual.php'
    assert calls[0][2]['data']=={'csrf':'test','chosen_year':'annual-2032','fetch':'Download'}
    monkeypatch.setattr('imd_data.requests.Session',lambda:pytest.fail('must use cache'))
    assert download_temperature(2032,product,tmp_path)==path


def test_temperature_download_follows_dated_binary_link(tmp_path,monkeypatch):
    raw=np.full((365,31,31),22,dtype='<f4').tobytes()
    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def get(self,url,**kwargs): return Response(b'<a href="data/MaxT_2023.GRD">2023</a>',url)
        def request(self,method,url,**kwargs):
            assert method=='GET'
            assert url.endswith('/data/MaxT_2023.GRD')
            return Response(raw,url)
    monkeypatch.setattr('imd_data.requests.Session',Session)
    assert download_temperature(2023,'tmax',tmp_path).stat().st_size==365*31*31*4


def test_temperature_html_error_is_not_cached(tmp_path,monkeypatch):
    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def get(self,url,**kwargs): return Response(b'<form action="annual.php"><select name="year"><option>2024</option></select></form>',url)
        def request(self,*args,**kwargs): return Response(b'<html>not available</html>',args[1])
    monkeypatch.setattr('imd_data.requests.Session',Session)
    with pytest.raises(ValueError): download_temperature(2024,'tmax',tmp_path)
    assert not list(tmp_path.iterdir())


def test_unpublished_year_is_clear(tmp_path,monkeypatch):
    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def get(self,url,**kwargs):return Response(b'<form action="annual.php"><select name="year"><option>2023</option></select></form>',url)
    monkeypatch.setattr('imd_data.requests.Session',Session)
    with pytest.raises(ValueError,match='2024|published'):download_temperature(2024,'tmax',tmp_path)


def test_external_download_target_is_rejected():
    from imd_sources import _download_request
    with pytest.raises(ValueError,match='destination'):
        _download_request('<a href="https://example.com/MaxT_2024.grd">2024</a>','https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html',2024)


def test_standalone_select_with_binary_urls():
    from imd_sources import _download_request
    method,url,fields=_download_request('<select onchange="location=this.value"><option value="data/tmax_2024.grd">2024</option></select>','https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html',2024)
    assert method=='GET'
    assert url.endswith('/Griddata/data/tmax_2024.grd')
    assert fields=={}


def test_get_form_with_followup_download_page(tmp_path,monkeypatch):
    raw=np.full((365,31,31),22,dtype='<f4').tobytes()
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,**kwargs):return Response(b'<form action="annual.php"><select name="year"><option>2023</option></select></form>',url)
        def request(self,method,url,**kwargs):
            if url.endswith('annual.php'):
                assert kwargs['params']=={'year':'2023'}
                return Response(b'<html><a href="max_2023.grd">Download 2023</a></html>',url)
            return Response(raw,url)
    monkeypatch.setattr('imd_data.requests.Session',Session)
    assert download_temperature(2023,'tmax',tmp_path).read_bytes()==raw


def test_download_discovery_preserves_selected_and_checked_controls():
    from imd_sources import _download_request
    html='''<form action="annual.php" method="post">
    <input name="token" type="hidden" value="abc">
    <input type="checkbox" name="accept" value="yes" checked>
    <input type="checkbox" name="unused" value="no">
    <input type="radio" name="mode" value="binary" checked>
    <input type="radio" name="mode" value="ascii">
    <select name="format"><option value="ascii">ASCII</option><option value="binary" selected>Binary</option></select>
    <select name="year"><option>2023</option><option>2024</option></select>
    </form>'''
    _,_,fields=_download_request(html,'https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html',2024)
    assert fields=={'token':'abc','accept':'yes','mode':'binary','format':'binary','year':'2024'}
