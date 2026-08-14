# Smoke Test Manual — AED Route Hamburg

Ejecutar tras CADA fase del plan de remediación
(`docs/superpowers/plans/2026-08-14-audit-remediation.md`), antes de dar la
fase por cerrada (`superpowers:verification-before-completion`). Si
cualquier paso falla: revertir el commit de la fase en curso y parar.

**Nota (Fase 0):** el puerto de arranque aún no está unificado (hallazgo
C7 — pendiente de decidirse en la Fase 3b). Hoy conviven 5050 (bloque
`__main__` de `app/app.py`) y 5000 (`app/wsgi.py`, `Dockerfile`,
`docker-compose.yml`, `docs/apache.conf`). Usar el puerto real que el
comando de arranque elegido efectivamente expone, no uno fijo de memoria.

1. **Arrancar el servidor:**
   ```bash
   .venv/bin/uvicorn app.app:app --host 0.0.0.0 --port <puerto vigente>
   ```
   Confirmar que aparece el log de arranque (`"FastAPI app ready."` — no
   `"Flask app ready."`, ver hallazgo C4) sin traceback, y que el proceso
   sigue vivo tras la carga del grafo (~20-30 s).

2. **Health check:**
   ```bash
   curl http://127.0.0.1:<puerto>/healthz
   ```
   Debe devolver `{"ok":true}`.

3. **Carga de la página raíz:** abrir `http://127.0.0.1:<puerto>/` en un
   navegador y confirmar visualmente las tres capas:
   - Puntos de AED (marcadores rojos)
   - Límite administrativo (polilínea azul)
   - Isócronas (activar el toggle correspondiente — capas verde/naranja)

   Nota (Fase 0 — hallazgo C1, pendiente de reverificación en Fase 1): la
   auditoría original afirmaba que `/` sirve `index_original.html`, cuyo
   frontend hace `fetch("./data/...")` relativo y esas tres capas fallarían
   con 404. Este paso del smoke test debe registrar explícitamente qué se
   observa realmente (capas visibles o no), no asumir el resultado.

4. **Ruta por click:** un click en el mapa debe devolver una ruta en cada
   uno de los tres modos (Walk, Bike, Car) — confirmar que se dibuja una
   polilínea y que la tarjeta de resultado muestra tiempo y distancia.

5. **Apagado limpio:** parar el servidor (Ctrl+C) y confirmar que no quedan
   procesos `uvicorn`/`python` huérfanos:
   ```bash
   pgrep -fl "uvicorn app.app:app"
   ```
   No debe devolver nada tras el apagado.

## Registro de ejecuciones

Cada fase añade aquí una línea al cerrar, con fecha, fase y resultado
(no se borra el historial — apéndice simple, no formato append-only estricto
como `docs/decisions.md`):

| Fecha | Fase | Resultado | Notas |
|---|---|---|---|
| 2026-08-14 | Fase 3(c) | OK (con limitación anotada) | Arranque OK, `/healthz` 200, `GET /` 200, `/api/aeds` 200. Apagado limpio. Limitación: el `.venv` no se recreó desde cero tras retirar `python-multipart`/`pyarrow` de `requirements.txt`, así que esto no prueba una instalación limpia sin esas dependencias — ver `docs/decisions.md`. |
| 2026-08-14 | Fase 3(a) | OK | Arranque OK (~5 s), `/healthz` 200. `POST /api/route` en los tres modos: walk → 3 resultados (165.8 s), bike → 3 resultados (65.7 s), car → 0 resultados (ya conocido, sin cambio respecto al baseline). Comportamiento idéntico al de antes de envolver la llamada en `asyncio.to_thread` — el cambio no altera resultados, solo concurrencia. Apagado limpio, sin procesos huérfanos. |
| 2026-08-14 | Fase 0 | Parcial — ver notas | Arranque OK (`.venv/bin/uvicorn app.app:app --host 127.0.0.1 --port 5000`, ~5 s hasta "FastAPI app ready."). `/healthz` → `{"ok":true}`. `GET /` → 200. `/api/aeds` → 141 features. `/api/boundary` → 200. `/api/isochrones` → 200. `POST /api/route` (origen aprox. Rathaus, 53.5503/9.9927): walk → 3 resultados (mejor 165.8 s), bike → 3 resultados (mejor 65.7 s), car → **0 resultados** (sin interpretar el motivo aquí — puede ser zona peatonal sin acceso rodado cercano; queda para análisis fuera de esta fase, no es un fallo de arranque). Pasos 3 y 4 del checklist (carga visual de las 3 capas en navegador, click real en el mapa) **NO se ejecutaron literalmente** — no hay navegador disponible en este entorno; se verificó el equivalente de backend (endpoints responden con datos válidos) pero no la renderización real del frontend. Este punto es precisamente el que la Fase 1 (hallazgo C1) va a investigar a fondo. Apagado limpio confirmado (sin procesos huérfanos tras `kill`). |
