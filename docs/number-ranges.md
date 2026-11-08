# Nummernkreise

Nummern werden ausschliesslich vom Generator (Tabelle number_ranges,
Service app/services/numbering.py) vergeben. Manuelle Nummern sind nicht
erlaubt; die API validiert das.

| Prefix | Objekt     | Format        | Beispiel    |
|--------|------------|---------------|-------------|
| P-     | Artikel    | P-000001      | P-000123    |
| ASM-   | Baugruppe  | ASM-000001    | ASM-000045  |
| DOC-   | Dokument   | DOC-000001    | DOC-000789  |
| ECR-   | Aenderungsantrag | ECR-2026-001 | ECR-2026-014 |
| ECO-   | Aenderungsauftrag | ECO-2026-001 | ECO-2026-003 |
| RPT-   | Report-Export    | RPT-2026-001 | RPT-2026-014 |

Klassifizierung der Artikel (Tabelle part_classes, per Migration geseedet):
MECH (Mechanik), ELEC (Elektronik), CONS (Consumables), PACK (Verpackung).

## Revisionschema

Fortlaufend numerisch, zweistellig, beginnt bei 01: 01, 02, 03 ...
Vorteil gegenueber A/B/C: sortierbar, keine Verwechslung mit
Format-Suffixen, maschinell erhoehbar (der Agent kann die naechste
freie Revision zuverlaessig vorschlagen).
