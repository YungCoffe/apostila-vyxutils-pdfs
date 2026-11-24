import hashlib, json, os, subprocess, time, traceback
from pathlib import Path
import requests, pymupdf

pairs = ['169678/1781599','169683/1781645','169673/1781562','169691/1781692','169695/1781734','169686/1781669','169718/1783558','169722/1783579','169714/1783527','169730/1783622','169734/1783646','169726/1783605','169761/1784592','169756/1784568','169766/1784616','169775/1784647','169770/1784631','169785/1784689','169800/1784773','169804/1784795']
items = [(s.split('/')[1],f'https://acervocmsp.educacao.sp.gov.br/{s}.pdf') for s in pairs]
items += [(n,f'https://github.com/YungCoffe/sp-acao-apostilas/releases/download/apostilas-2026/{n}.pdf') for n in ('portugues1','portugues2','portugues3','matematica1','matematica2','matematica3')]
repo = os.environ['GITHUB_REPOSITORY']; tag='apostilas-2026-vyxutils'
session=requests.Session(); session.headers['User-Agent']='Apostila-VyxUtils/1.0'

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def gh(*args):
 subprocess.run(['gh',*args,'--repo',repo],check=True)
def fetch(url,path):
 for attempt in range(3):
  try:
   with session.get(url,stream=True,timeout=(30,180)) as r:
    r.raise_for_status()
    with open(path,'wb') as f:
     for chunk in r.iter_content(1024*1024):
      if chunk:f.write(chunk)
   if Path(path).stat().st_size<100 or open(path,'rb').read(5)!=b'%PDF-':raise ValueError('Resposta não é PDF')
   return
  except Exception:
   Path(path).unlink(missing_ok=True)
   if attempt==2: raise
   time.sleep(3*(attempt+1))
def check_remote(url,expected):
 h=hashlib.sha256()
 with session.get(url,stream=True,timeout=(30,180),headers={'Cache-Control':'no-cache'}) as r:
  r.raise_for_status()
  for b in r.iter_content(1024*1024):
   if b:h.update(b)
 if h.hexdigest()!=expected:raise ValueError('SHA-256 público divergente')

# Create the public release once, and never overwrite an existing asset.
if subprocess.run(['gh','release','view',tag,'--repo',repo],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
 gh('release','create',tag,'--title','Apostilas 2026 — VyxUtils','--notes','PDFs com a marca roxa VyxUtils em todas as páginas. Consulte o manifesto para status e SHA-256.')
results=[]
for name,url in items:
 src=Path('/tmp/apostila-original.pdf'); out=Path('/tmp')/(name+'-VyxUtils.pdf')
 r={'nome':name,'fonte':url}
 try:
  print('INICIANDO',name,flush=True); fetch(url,src)
  r['original_sha256']=sha(src)
  with pymupdf.open(src) as doc:
   if doc.needs_pass or not doc.page_count:raise ValueError('PDF vazio ou bloqueado')
   r['paginas']=doc.page_count
   for page in doc:
    rect=page.rect; fs=max(5,min(9,rect.width/60)); width=pymupdf.get_text_length('VyxUtils',fontname='helv',fontsize=fs)
    point=pymupdf.Point(rect.x1-width-10,rect.y1-8)*page.derotation_matrix
    page.insert_text(point,'VyxUtils',fontsize=fs,fontname='helv',color=(.49,.20,.75),overlay=True,rotate=page.rotation)
   doc.save(out,garbage=3,deflate=True)
  with pymupdf.open(out) as doc:
   if doc.page_count!=r['paginas']:raise ValueError('contagem de páginas divergente')
   missing=[p.number+1 for p in doc if 'VyxUtils' not in p.get_text()]
   if missing:raise ValueError('marca ausente nas páginas '+str(missing[:30]))
   for i in sorted({0,doc.page_count//2,doc.page_count-1}): doc[i].get_pixmap(matrix=pymupdf.Matrix(.35,.35),alpha=False)
  r['sha256']=sha(out); r['bytes']=out.stat().st_size
  public=f'https://github.com/{repo}/releases/download/{tag}/{out.name}'
  # Do not overwrite: if an asset already exists, verify it matches this generation.
  exists=subprocess.run(['gh','release','view',tag,'--repo',repo,'--json','assets','--jq',f'.assets[].name | select(. == "{out.name}")'],capture_output=True,text=True,check=True).stdout.strip()
  if not exists: gh('release','upload',tag,str(out))
  check_remote(public,r['sha256'])
  r['url']=public; r['verificacao']='marca detectada em todas as páginas; 3 páginas renderizadas; SHA-256 público confere'
  print('PUBLICADO',name,public,flush=True)
 except Exception as e:
  r['erro']=str(e); print('FALHA',name,repr(e),traceback.format_exc(),flush=True)
 finally:
  src.unlink(missing_ok=True); out.unlink(missing_ok=True)
  results.append(r)
  Path('manifesto-vyxutils.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
# Publish manifest last as an audit record; no overwrite of prior manifest.
try: gh('release','upload',tag,'manifesto-vyxutils.json')
except Exception as e: print('FALHA MANIFESTO',repr(e),flush=True)
print('RESUMO',json.dumps({'total':len(items),'publicados_verificados':sum('url' in r for r in results),'falhas':[r['nome'] for r in results if 'erro' in r]},ensure_ascii=False),flush=True)
if any('erro' in r for r in results):raise SystemExit(1)
