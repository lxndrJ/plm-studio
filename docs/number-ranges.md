# Number ranges

Numbers are assigned exclusively by the generator (table number_ranges,
service app/services/numbering.py). Manual numbers are not allowed; the API
validates this.

| Prefix | Object            | Format     | Example   |
|--------|-------------------|------------|-----------|
| P-     | Part              | P-000001   | P-000123  |
| ASM-   | Assembly          | ASM-000001 | ASM-000045|
| DOC-   | Document          | DOC-000001 | DOC-000789|
| ECR-   | Change request    | ECR-00001  | ECR-00014 |
| ECO-   | Change order      | ECO-00001  | ECO-00003 |
| RPT-   | Report export     | RPT-00001  | RPT-00014 |

Part classification (table part_classes, seeded by migration):
MECH (mechanical), ELEC (electronics), CONS (consumables), PACK (packaging).

## Revision scheme

Sequential numeric, two digits, starting at 01: 01, 02, 03 ...
Advantage over A/B/C: sortable, no confusion with format suffixes,
machine-incrementable (the agent can reliably propose the next free
revision). A year component in ECR/ECO/RPT numbers (e.g. ECR-2026-001)
is planned for M6.
