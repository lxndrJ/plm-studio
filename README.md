# PLM Studio

Eigenbau-PLM mit KI-Prompt-Layer. Artikel, Revisionen, mehrstufige
Stuecklisten, Dokumente (Vector/JPEG/CAD) mit Preview-Pipeline,
ECR/ECO-Workflow, Audit-Trail und versionierten PDF-Reports.

Der vollstaendige Blueprint (Architektur, ER-Modell, Milestones M0-M7)
liegt im Projektdokument "PLM-System Blueprint".

## Status

- [x] M0 Repo, Docker Compose, CI
- [ ] M1 Datenmodell und Alembic-Migrationen (Schema liegt bei, Tests folgen)
- [ ] M2 Artikel, Revisionen, Nummernkreis
- [ ] M3 BOM und Where-Used
- [ ] M4 Dokumente und Preview-Pipeline
- [ ] M5 Workflow, ECR/ECO
- [ ] M6 Report-Engine
- [ ] M7 KI-Layer (LiteLLM, Tools, Guardrails)

## Quickstart

    cp .env.example .env
    docker compose up -d db
    cd backend
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    alembic upgrade head
    uvicorn app.main:app --reload
    # API-Dokumentation: http://localhost:8000/docs

Tests:

    pytest tests
    TEST_DATABASE_URL=postgresql+psycopg://plm:plm@localhost:5432/plm_test pytest

## Kernprinzipien

1. Das LLM ruft nie direkt die DB auf, nur Tool-Funktionen der PLM-API.
2. Schreibende Operationen laufen ueber Confirmation-Tokens.
3. Freigegebene Revisionen sind immutable (DB-Trigger erzwingt es).
4. Jede Aenderung landet im append-only Audit-Log.
5. Workflow-Spruenge sind Datensaetze in workflow_transitions, nicht Code.

Entscheidungen und Begruendungen: docs/adr/. Nummernkreise: docs/number-ranges.md.
