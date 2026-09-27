"""Sondes de métadonnées uniquement ; aucun téléchargement de ROM/jaquette."""
import json
import requests
from pathlib import Path
from romget.config import Config
out={}
url='https://archive.org/advancedsearch.php'
try:
 r=requests.get(url,params={'q':'title:(gran turismo 4) AND mediatype:software','rows':2,'output':'json','fl[]':['identifier','title']},timeout=15)
 out['ia_search']={'status':r.status_code}
 if r.ok:
  data=r.json()['response'];out['ia_search']['numFound']=data.get('numFound')
  out['ia_search']['returned']=len(data.get('docs',[]))
except requests.RequestException as e: out['ia_search']={'error_type':type(e).__name__}
key=Config.load().steamgrid_api_key
for name,path,params in [('sgdb_current','/search/autocomplete',{'term':'Gran Turismo 4'}),('sgdb_path','/search/autocomplete/Gran%20Turismo%204',{})]:
 try:
  r=requests.get('https://www.steamgriddb.com/api/v2'+path,params=params,headers={'Authorization':'Bearer '+key},timeout=15)
  out[name]={'status':r.status_code,'content_type':r.headers.get('content-type')}
  if r.ok:
   d=r.json();out[name]['results']=len(d.get('data',[]))
 except requests.RequestException as e: out[name]={'error_type':type(e).__name__}
print(json.dumps(out,indent=2))
Path('audit/network-results.json').write_text(json.dumps(out,indent=2)+'\n')
