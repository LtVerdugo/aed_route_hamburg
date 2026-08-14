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
