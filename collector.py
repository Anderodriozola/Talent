from __future__ import annotations
import json, re, hashlib, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

SOURCES = [
 {"name":"Batea","url":"https://empleo.batea.com/jobs"},
 {"name":"Campo & Ochandiano","url":"https://www.campo-ochandiano.com/ofertas/list"},
 {"name":"Michael Page","url":"https://www.michaelpage.es/jobs/marketing/basque-country/pa%C3%ADs-vasco"},
 {"name":"Robert Walters","url":"https://www.robertwalters.es/ofertas-de-empleo/bilbao.html"},
 {"name":"Ferruelo & Velasco","url":"https://ofertas.ferrueloyvelasco.com/"},
 {"name":"Deusto Alumni","url":"https://alumni.deusto.es/s/ofertas-empleo?language=es"},
 {"name":"Deusto Business Alumni","url":"https://www.deustobusinessalumni.es/s/buscador-ofertas"},
 {"name":"Selección & Formación","url":"https://www.seleccionformacion.com/ofertas/Default.aspx"},
 {"name":"AdegiLan","url":"https://www.adegi.es/adegilan/es/"},
 {"name":"Guggenheim Bilbao","url":"https://www.guggenheim-bilbao.eus/empleo-y-practicas/ofertas-de-empleo"},
]
INCLUDE = ["marketing","comunicación","comunicacion","publicidad","prensa","relaciones públicas","relaciones publicas","social media","community manager","content","contenidos","copywriter","copywriting","branding","marca","eventos","patrocinios","seo","sem","paid media","performance","crm","email marketing","audiovisual","producción audiovisual","produccion audiovisual","promoción","promocion","festival","música","musica","cine","creative","creatividad"]
EXCLUDE = ["ingeniero","ingeniera","ingeniería","ingenieria","mantenimiento","contable","contabilidad","controller","finanzas","financiero","enfermería","enfermeria","médico","medico","programador","developer","sistemas","logística","logistica","compras","calidad","prl","producción industrial","produccion industrial"]
HEADERS={"User-Agent":"TalentJobs/1.0 (+https://anderodriozola.github.io/Talent/)","Accept-Language":"es-ES,es;q=0.9,en;q=0.6"}

def clean(x): return re.sub(r"\s+"," ",str(x or "")).strip()
def relevant(text):
 t=clean(text).lower()
 return any(k in t for k in INCLUDE) and not any(k in t for k in EXCLUDE)
def category(text):
 t=text.lower()
 for keys,cat in [(["seo","sem","paid media","performance"],"Marketing digital"),(["social media","community"],"Social media"),(["evento","festival","patrocin"],"Eventos"),(["content","contenido","copy"],"Contenidos"),(["prensa","relaciones públicas","relaciones publicas"],"RRPP y prensa"),(["branding","marca"],"Marca y branding"),(["publicidad","creative","creativ"],"Publicidad y creatividad"),(["marketing"],"Marketing")]:
  if any(k in t for k in keys): return cat
 return "Comunicación"
def province(text):
 t=text.lower()
 if any(x in t for x in ["bilbao","bizkaia","vizcaya","zamudio","getxo","barakaldo"]): return "Bizkaia"
 if any(x in t for x in ["donostia","san sebastián","san sebastian","gipuzkoa","guipúzcoa","guipuzcoa","irun","eibar","oñati","mondragón","mondragon"]): return "Gipuzkoa"
 if any(x in t for x in ["vitoria","gasteiz","álava","alava","araba"]): return "Álava"
 if "remoto" in t or "remote" in t: return "Remoto"
 return "Euskadi"
def add(out, seen, *, title, url, source, company="", location="", date=""):
 title=clean(title); url=clean(url)
 if len(title)<4 or not url or not relevant(title+" "+company): return
 key=hashlib.sha1((title.lower()+"|"+clean(company).lower()+"|"+url.split('?')[0]).encode()).hexdigest()
 if key in seen:return
 seen.add(key); text=" ".join([title,company,location])
 out.append({"id":key[:12],"title":title[:180],"company":clean(company)[:120],"location":clean(location)[:100] or province(text),"province":province(text),"category":category(text),"date":clean(date)[:40],"url":url,"source":source,"is_new":True})
def walk_json(obj):
 if isinstance(obj,dict):
  if obj.get("@type") in ("JobPosting",["JobPosting"]): yield obj
  for v in obj.values(): yield from walk_json(v)
 elif isinstance(obj,list):
  for v in obj: yield from walk_json(v)
def fetch_source(src,out,seen,errors):
 try:
  r=requests.get(src["url"],headers=HEADERS,timeout=35); r.raise_for_status(); soup=BeautifulSoup(r.text,"html.parser")
  before=len(out)
  for tag in soup.select('script[type="application/ld+json"]'):
   try:
    data=json.loads(tag.get_text(strip=True))
    for j in walk_json(data):
     loc=j.get("jobLocation",{}); loc=loc[0] if isinstance(loc,list) and loc else loc
     addr=loc.get("address",{}) if isinstance(loc,dict) else {}
     add(out,seen,title=j.get("title"),url=j.get("url") or src["url"],source=src["name"],company=(j.get("hiringOrganization") or {}).get("name",""),location=", ".join(filter(None,[addr.get("addressLocality"),addr.get("addressRegion")])),date=j.get("datePosted",""))
   except Exception: pass
  # Fallback for public lists: keep only links whose visible title clearly matches the editorial filter.
  for a in soup.find_all("a",href=True):
   title=clean(a.get_text(" ",strip=True))
   href=urljoin(src["url"],a["href"])
   if urlparse(href).netloc and relevant(title): add(out,seen,title=title,url=href,source=src["name"],location=title)
  if len(out)==before: errors.append({"source":src["name"],"message":"Sin ofertas compatibles detectadas"})
 except Exception as e: errors.append({"source":src["name"],"message":clean(e)[:160]})
def main():
 old={}
 p=Path("jobs.json")
 if p.exists():
  try: old={j.get("id"):j for j in json.loads(p.read_text(encoding="utf-8")).get("jobs",[])}
  except Exception: pass
 out=[];seen=set();errors=[]
 for s in SOURCES: fetch_source(s,out,seen,errors)
 for j in out: j["is_new"]=j["id"] not in old
 out.sort(key=lambda j:(not j["is_new"],j["source"].lower(),j["title"].lower()))
 now=datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
 p.write_text(json.dumps({"updated_at":now,"jobs":out,"source_status":errors},ensure_ascii=False,indent=2),encoding="utf-8")
 print(f"Generadas {len(out)} ofertas; {len(errors)} avisos de fuente")
if __name__=="__main__": main()
