from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BATEA_URL = "https://empleo.batea.com/jobs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TalentJobs/1.0; +https://anderodriozola.github.io/Talent/)",
    "Accept-Language": "es-ES,es;q=0.9",
}

ROLE_TERMS = (
    "director", "directora", "dirección", "direccion", "responsable", "manager",
    "head", "técnico", "técnica", "tecnico", "tecnica", "especialista",
    "coordinador", "coordinadora", "consultor", "consultora", "gestor", "gestora",
    "executive", "lead", "project manager", "community manager", "copywriter"
)
DOMAIN_TERMS = (
    "marketing", "comunicación", "comunicacion", "publicidad", "relaciones públicas",
    "relaciones publicas", "prensa", "social media", "community", "contenido", "content",
    "copy", "branding", "marca", "eventos", "patrocin", "seo", "sem", "paid media",
    "audiovisual", "promoción", "promocion", "creative", "creatividad"
)
BLOCK_TERMS = (
    "acerca del museo", "amigos del museo", "canal audiovisual", "área de prensa",
    "area de prensa", "colección", "coleccion", "obras de", "agenda", "visita",
    "exposición", "exposicion", "noticia", "blog", "contacto", "cookies",
    "política de privacidad", "politica de privacidad"
)
STRATEGIC_EXCEPTIONS = (
    "coordinador/a general (zineuskadi)",
    "coordinador general (zineuskadi)",
    "coordinadora general (zineuskadi)",
)


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def is_real_job_link(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.netloc == "empleo.batea.com"
        and re.fullmatch(r"/jobs/\d+-[^/]+", parsed.path.rstrip("/")) is not None
    )


def is_relevant(title: str) -> bool:
    text = clean(title).lower()
    if any(term in text for term in BLOCK_TERMS):
        return False
    if any(exception in text for exception in STRATEGIC_EXCEPTIONS):
        return True
    has_role = any(term in text for term in ROLE_TERMS)
    has_domain = any(term in text for term in DOMAIN_TERMS)
    return has_role and has_domain


def category(title: str) -> str:
    text = title.lower()
    if "zineuskadi" in text:
        return "Cultura y audiovisual"
    if any(x in text for x in ("seo", "sem", "paid media")):
        return "Marketing digital"
    if any(x in text for x in ("social media", "community")):
        return "Social media"
    if any(x in text for x in ("evento", "patrocin")):
        return "Eventos"
    if any(x in text for x in ("content", "contenido", "copy")):
        return "Contenidos"
    if any(x in text for x in ("relaciones públicas", "relaciones publicas", "prensa")):
        return "RRPP y prensa"
    if any(x in text for x in ("branding", "marca")):
        return "Marca y branding"
    if "marketing" in text:
        return "Marketing"
    return "Comunicación"


def province(location: str) -> str:
    text = location.lower()
    if any(x in text for x in ("bilbao", "bizkaia", "vizcaya")):
        return "Bizkaia"
    if any(x in text for x in ("donostia", "gipuzkoa", "guipúzcoa", "guipuzcoa", "deba", "urola", "tolosa")):
        return "Gipuzkoa"
    if any(x in text for x in ("vitoria", "gasteiz", "álava", "alava", "araba")):
        return "Álava"
    return "Euskadi"


def scrape_batea() -> list[dict]:
    response = requests.get(BATEA_URL, headers=HEADERS, timeout=40)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    jobs, seen = [], set()

    for link in soup.find_all("a", href=True):
        url = urljoin(BATEA_URL, link["href"])
        if not is_real_job_link(url):
            continue

        strings = [clean(x) for x in link.stripped_strings if clean(x)]
        if not strings:
            continue

        title = strings[0]
        if not is_relevant(title):
            continue

        location = strings[1] if len(strings) > 1 else "Euskadi"
        job_id = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        if job_id in seen:
            continue
        seen.add(job_id)

        jobs.append({
            "id": job_id,
            "title": title[:180],
            "company": "Empresa no indicada",
            "location": location[:100],
            "province": province(location),
            "category": category(title),
            "date": "",
            "url": url,
            "source": "Batea",
            "is_new": True,
        })
    return jobs


def main() -> None:
    output = Path("jobs.json")
    old_ids = set()
    if output.exists():
        try:
            old = json.loads(output.read_text(encoding="utf-8"))
            old_ids = {job.get("id") for job in old.get("jobs", [])}
        except Exception:
            pass

    jobs = scrape_batea()
    if not jobs:
        raise RuntimeError(
            "Batea respondió, pero no se detectó ninguna oferta laboral compatible. "
            "No se sobrescribe jobs.json."
        )

    for job in jobs:
        job["is_new"] = job["id"] not in old_ids

    jobs.sort(key=lambda job: (not job["is_new"], job["title"].lower()))
    payload = {
        "updated_at": datetime.now().astimezone().strftime("%d/%m/%Y %H:%M"),
        "jobs": jobs,
        "source_status": [{"source": "Batea", "status": "OK", "detected": len(jobs)}],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Batea: {len(jobs)} ofertas laborales compatibles guardadas")


if __name__ == "__main__":
    main()
