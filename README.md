# Talent

Portal privado-compartible de ofertas de marketing, comunicación, publicidad, contenidos y eventos en Euskadi.

## Funcionamiento
- `index.html` muestra y filtra `jobs.json`.
- `collector.py` consulta las fuentes públicas configuradas, filtra y elimina duplicados.
- GitHub Actions ejecuta la actualización cada noche a las 02:30, zona `Europe/Madrid`.
- También puede ejecutarse manualmente desde **Actions > Actualizar ofertas > Run workflow**.

## Importante
La extracción web es dependiente de la estructura pública de cada fuente. Si una web cambia, esa fuente puede dejar de aportar resultados sin impedir que funcionen las demás. `jobs.json` incluye `source_status` para diagnóstico.

InfoJobs no se conecta todavía: su API oficial exige registrar una aplicación y credenciales. No publiques credenciales en archivos; cuando las tengas, guárdalas como GitHub Actions Secrets.
