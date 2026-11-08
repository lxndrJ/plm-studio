# AGENTS.md - Regeln fuer Vibe Code in diesem Repo

Projekt: PLM Studio (Eigenbau-PLM mit KI-Prompt-Layer).
Stack: FastAPI (Python 3.12) + PostgreSQL 16 + Alembic + SvelteKit.
Blueprint und Milestones M0-M7: siehe README.md und docs/.

## Arbeitsweise

- TDD fuer Geschaeftsregeln: zuerst der Test (tests/), dann die
  Implementierung. Abnahmekriterien je Meilenstein stehen im README.
- Jede Schema-Aenderung nur ueber eine neue Alembic-Migration
  (alembic revision), nie manuell in der DB.
- Conventional Commits, kleine reviewbare Aenderungen.
- Ruff (line-length 100) und pytest muessen vor jedem Commit gruen sein.

## PLM-Datenregeln (kritisch, niemals verletzen)

1. Teilenummern vergibt ausschliesslich der Nummernkreis-Generator
   (app/services/numbering.py). Niemals client-seitig Nummern setzen.
2. Freigegebene Revisionen (status=released) sind immutable; ein
   DB-Trigger erzwingt das. Aenderungen laufen immer ueber neue
   Revisionen mit change_reason.
3. Statusuebergaenge nur ueber die Matrix in workflow_transitions;
   nie einen status direkt UPDATE'n.
4. Jeder schreibende Vorgang erzeugt einen audit_log-Eintrag
   (who/what/why/old/new).
5. Kein Artikel ohne Klassifizierung, keine BOM-Position ohne
   gueltige Artikelreferenz, kein DELETE an released Objekten.
6. Schreibende API-Operationen sind Proposed-Writes mit
   Confirmation-Token (siehe app/guardrails/confirmations.py).

## Naechster Meilenstein (M2)

Revisionen-Endpoint (POST /parts/{pn}/revisions), Transition-Endpoint
(POST /revisions/{id}/transition) mit Rechtepruefung gegen
workflow_transitions, Search/Filter fuer GET /parts.
