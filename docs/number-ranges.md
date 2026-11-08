# Nummernkreise

Nummern werden ausschliesslich vom Generator (Tabelle number_ranges,
Service app/services/numbering.py) vergeben. Manuelle Nummern sind nicht
erlaubt; die API validiert das.

| Prefix | Objekt     | Format        | Beispiel    |
|--------|------------|---------------|-------------|
| P-     | Artikel    | P-000001      | P-000123    |
| ASM-   | Baugruppe  | ASM-000001    | ASM-000045  |
| DOC-   | Dokument   | DOC-000001    | DOC-000789  |
| ECR-   | Aenderungsantrag | ECR-00001 | ECR-00014 |
| ECO-   | Aenderungsauftrag | ECO-00001 | ECO-00003 |
| RPT-   | Report-Export    | RPT-00001 | RPT-00014 |

Klassifizierung der Artikel (Tabelle part_classes, per Migration geseedet):
MECH (Mechanik), ELEC (Elektronik), CONS (Consumables), PACK (Verpackung).

## Revisionschema

Fortlaufend numerisch, zweistellig, beginnt bei 01: 01, 02, 03 ...
Vorteil gegenueber A/B/C: sortierbar, keine Verwechslung mit
Format-Suffixen, maschinell erhoehbar (der Agent kann die naechste
freie Revision zuverlaessig vorschlagen). Jahresanteil in ECR/ECO/RPT
(z. B. ECR-2026-001) ist fuer M6 vorgesehen.
