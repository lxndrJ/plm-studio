# ADR 0001: Tech-Stack fuer das Eigenbau-PLM

Status: akzeptiert (2026-11-08)

## Kontext

Kleines Team, self-hosted auf VPS ( Raspberry Pi als Testmoeglichkeit),
KI-Prompt-Layer als Primaer-Benutzerschnittstelle, intern Dateiverwaltung
fuer Vector/JPEG und Report-Generierung fuer Externe.

## Entscheidung

PostgreSQL 16 als Datenbank, FastAPI (Python 3.12) als Backend,
LiteLLM als OpenAI-kompatibler Modell-Proxy, SvelteKit als Frontend,
Docker Compose als Deployment, Typst fuer Reports.

## Begruendung

- PostgreSQL: relationale Integritaet fuer Teile-/BOM-Referenzen,
  Recursive CTEs fuer Where-Used, JSONB fuer flexible Attribute.
- FastAPI: generiert automatisch ein OpenAPI-Schema. Dieses Schema ist
  spaeter wortwoertlich der Tool-Contract des KI-Agenten. Eine zweite,
  abweichende Tool-Beschreibung entfaellt damit.
- LiteLLM: Modelle (Mistral/DeepSeek/lokal) austauschbar ohne Codeaenderung,
  Kostenkontrolle zentral.
- Typst: PDF-Generierung ohne headless Chrome, lauffaehig auf ARM.

## Alternativen (verworfen)

- Wrapper um Aras/OpenPLM: Agent-Layer statt Kern bedeutet, dass die
  Datenintegraetsregeln (Immutability, Workflow) vom Fremdsystem abhaengen;
  fuer ein kleines Team unnoetige Betriebslast. Entscheidung fiel bewusst
  fuer Kompletteigenbau.
- Node/NestJS Backend: gleichfaehig, aber Python-Oekosystem fuer CAD/Material
  (OCC, stepler, pandas) passt besser in ein PLM-Umfeld.
- MongoDB: referentielle Integritaet (keine BOM-Position ohne gueltige
  Artikelreferenz) ist eine Kernanforderung, relationale DB erzwingt sie.
- Keycloak: fuer ein kleines Team ueberdimensioniert; JWT reicht.

## Konsequenzen

- Alle Geschaefzregeln muessen selbst implementiert und getestet werden
  (Migrationspflicht fuer jede Regel).
- OpenAPI-Schema ist Teil des oeffentlichen Contracts: Breaking Changes
  brauchen eine neue API-Version.
