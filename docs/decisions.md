# Decisiones — Remediación de auditoría AED Route Hamburg

Log append-only. No editar entradas existentes; añadir nuevas al final.
Formato: `## YYYY-MM-DD — <decisión> — motivo: ... — cierra: <hallazgo o N/A>`

---

## 2026-08-14 — El commit baseline usa el prefijo `chore:`, no `fase 0:` — motivo: es pre-fase por diseño — cierra: N/A (convención de proceso)

El commit baseline (`860b5d7`, rama `main`) se titula
`chore: baseline commit (pre-remediation) — ...` en vez de seguir el
formato `fase N: <qué cambia>` acordado para el resto del plan (ver
Regla Global 3, 2026-08-14). Es intencional: ese commit captura el estado
del proyecto ANTES de cualquier remediación y es el único punto de retorno
de todo el plan — no se enmienda por consistencia cosmética. La convención
`fase N: ...` arranca desde el primer commit hecho en la rama de
remediación (`remediation/audit-2026-08`), en adelante.

---

## 2026-08-14 — Respaldo externo de `data/interim/hamburg_graph.pkl` (y del resto del proyecto) confirmado en Google Drive — motivo: `data/` está gitignorado por diseño (364 MB de cachés) — cierra: punto 2 del cierre de Fase 0

`data/interim/hamburg_graph.pkl` (364 MB) y el resto del proyecto están
subidos a Google Drive; la subida y su verificación fueron hechas
manualmente por el propietario del proyecto, fuera de esta sesión — no se
ha intentado ni se intentará automatizar esa subida ni crear una copia
local secundaria desde aquí. Como `data/` queda fuera de control de
versiones (`.gitignore`, ver commit baseline `860b5d7`), este respaldo
externo es el único mecanismo de recuperación de esos artefactos si se
perdieran localmente. Integridad verificable localmente vía
`data/interim/hamburg_graph.pkl.sha256` (creado en la Fase 0), que sí está
versionado.

Además, en esta misma fecha se aplicó `chmod 444` a
`data/interim/hamburg_graph.pkl`: dado que el grafo es inmutable durante
las 8 fases del plan (Restricción Global 1), este permiso hace que esa
inmutabilidad la imponga el sistema de archivos y no solo la disciplina del
plan. Si alguna operación futura falla por permisos sobre ese archivo
específico, es la salvaguarda funcionando como se pretende — no se debe
revertir el `chmod` para sortearla sin decisión explícita.
