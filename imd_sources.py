"""Discover annual temperature downloads from IMD's published HTML controls.

Download targets and field names come from the live page, never a guessed PHP API.
"""
from html.parser import HTMLParser
import io
from pathlib import Path
import re
import tempfile
from urllib.parse import urljoin, urlsplit
import zipfile

import requests

TEMPERATURE_PAGES = {
    'tmax': 'https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html',
    'tmin': 'https://www.imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html',
}


class DownloadPage(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.forms, self.links, self.options = [], [], []
        self.form = self.select = self.option = self.anchor = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            self.form = {'action':a.get('action',''), 'method':a.get('method','get').upper(), 'fields':{}, 'selects':{}}
            self.forms.append(self.form)
        elif tag == 'input' and self.form is not None and a.get('name') and 'disabled' not in a:
            kind = a.get('type','text').lower()
            if kind not in {'file','reset','button'} and (kind not in {'checkbox','radio'} or 'checked' in a):
                self.form['fields'][a['name']] = a.get('value','on' if kind in {'checkbox','radio'} else '')
        elif tag == 'select' and 'disabled' not in a:
            self.select = a.get('name','')
            if self.form is not None and self.select:
                self.form['selects'][self.select] = []
        elif tag == 'option' and self.select is not None:
            self.option = {'value':a.get('value'), 'text':'', 'disabled':'disabled' in a, 'selected':'selected' in a}
            self.options.append(self.option)
            if self.form is not None and self.select:
                self.form['selects'][self.select].append(self.option)
        elif tag == 'button' and self.form is not None and a.get('name') and a.get('type','submit').lower() == 'submit':
            self.form['fields'][a['name']] = a.get('value','')
        elif tag == 'a' and a.get('href'):
            self.anchor = {'href':a['href'],'text':''}
            self.links.append(self.anchor)

    def handle_data(self, data):
        if self.option is not None: self.option['text'] += data
        if self.anchor is not None: self.anchor['text'] += data

    def handle_endtag(self, tag):
        if tag == 'form': self.form = self.select = self.option = None
        elif tag == 'select': self.select = self.option = None
        elif tag == 'option': self.option = None
        elif tag == 'a': self.anchor = None


def _imd_url(base, target):
    url = urljoin(base,target)
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'www.imdpune.gov.in','imdpune.gov.in'} or parsed.port not in {None,443} or parsed.username or parsed.password:
        raise ValueError('IMD download page points to an unsupported destination.')
    return url


def _download_request(html, base, year):
    page = DownloadPage(html)
    year_pattern = rf'(?<!\d){year}(?!\d)'
    for link in page.links:
        if re.search(r'\.(grd|bin|zip)(?:[?#]|$)',link['href'],re.I) and re.search(year_pattern,link['href']+' '+link['text']):
            return 'GET',_imd_url(base,link['href']),{}
    for option in page.options:
        value=option['value'] or ''
        if not option['disabled'] and re.search(r'\.(grd|bin|zip)(?:[?#]|$)',value,re.I) and re.search(year_pattern,value+' '+option['text']):
            return 'GET',_imd_url(base,value),{}
    for form in page.forms:
        for name,options in form['selects'].items():
            for option in options:
                value = option['value'] if option['value'] is not None else option['text'].strip()
                if not option['disabled'] and re.search(year_pattern,value+' '+option['text']):
                    fields = form['fields'].copy()
                    for other,choices in form['selects'].items():
                        usable = [o for o in choices if not o['disabled']]
                        if usable:
                            default = next((o for o in usable if o['selected']),usable[0])
                            fields[other] = default['value'] if default['value'] is not None else default['text'].strip()
                    fields[name] = value
                    if form['method'] not in {'GET','POST'}:
                        raise ValueError('Unsupported method on IMD download form.')
                    return form['method'],_imd_url(base,form['action']),fields
    raise ValueError(f'No published annual binary link or year-select form for {year}. IMD may not have published this year, or its page format has changed.')


def download_temperature(year, product='tmax', folder='imd_netcdf_files', byte_order='<'):
    """Retrieve selected year's binary, validate it, and atomically publish cache."""
    from imd_data import read_binary
    if product not in TEMPERATURE_PAGES or not isinstance(year,int) or not 1678<=year<=2260 or byte_order not in {'<','>'}:
        raise ValueError('Choose Tmax/Tmin, a valid binary year, and byte order.')
    root = Path(folder)
    root.mkdir(parents=True,exist_ok=True)
    target = root/f'{product.upper()}_{year}.grd'
    if target.exists():
        read_binary(target.read_bytes(),product,year,byte_order)
        return target
    landing = TEMPERATURE_PAGES[product]
    with requests.Session() as session:
        page = session.get(landing,timeout=(15,90))
        page.raise_for_status()
        base = _imd_url(landing,page.url)
        method,url,fields = _download_request(page.text,base,year)
        # Some IMD form handlers return a page containing the final binary link.
        for hop in range(2):
            with session.request(method,url,**{'data' if method=='POST' else 'params':fields},
                                 headers={'Referer':base},stream=True,timeout=(15,180)) as response:
                response.raise_for_status()
                final_url = _imd_url(url,response.url)
                chunks,total = [],0
                for chunk in response.iter_content(1024*1024):
                    total += len(chunk)
                    if total > 16_000_000:
                        raise ValueError('Temperature response exceeds the annual binary size limit.')
                    chunks.append(chunk)
                raw = b''.join(chunks)
            if raw.lstrip().lower().startswith((b'<!doctype',b'<html',b'<form',b'<head',b'<body',b'<a ',b'<script')):
                if hop == 1:
                    raise ValueError('IMD returned HTML instead of an annual temperature file.')
                base=final_url
                method,url,fields = _download_request(raw.decode('utf-8',errors='replace'),final_url,year)
                continue
            break
    if raw.startswith(b'PK'):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            files = [f for f in archive.infolist() if not f.is_dir() and Path(f.filename).suffix.lower() in {'.grd','.bin'}]
            if len(files)!=1 or files[0].file_size > 16_000_000:
                raise ValueError('Expected one annual binary in the IMD ZIP response.')
            raw = archive.read(files[0])
    read_binary(raw,product,year,byte_order)
    part = None
    try:
        with tempfile.NamedTemporaryFile(dir=root,suffix='.part',delete=False) as f:
            part=Path(f.name)
            f.write(raw)
        part.replace(target)
    finally:
        if part is not None: part.unlink(missing_ok=True)
    return target
