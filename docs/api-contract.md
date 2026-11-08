# API-Contract fuer den KI-Agenten

Diese Regeln gelten fuer jeden Client der PLM-API, insbesondere fuer den
KI-Agenten. Das Backend erzwingt sie technisch; der Agent haelt sie
zusaetzlich ein (Defense in Depth).

1. Nur dokumentierte Endpunkte und Feldnamen verwenden. Das OpenAPI-Schema
   unter /openapi.json ist die einzige Quelle der Wahrheit.
2. Pflichtfelder validieren, bevor schreibende Calls gehen.
3. Schreibende Operationen laufen als Proposed-Write mit
   Confirmation-Token: 202 zurueck, User bestaetigt, erst dann execute.
4. Erst GET (aktueller Zustand), dann Mutation, dann GET (Verifikation).
5. Mehrstufige Aenderungen (Artikel + BOM + Dokument) in einer
   Transaktion bzw. in einem Batch, wenn der Endpoint es anbietet.
6. Rate-Limits und Fehlercodes: 429/5xx mit Exponential-Backoff,
   max. 3 Versuche, danach dem Nutzer melden.
7. Teilenummern werden NUR vom Nummernkreis-Generator vergeben, nie
   vom Agenten vorgeschlagen oder manuell gesetzt.
8. Duplikatpruefung vor jedem Anlegen: Suchtreffer sind dem Nutzer zu
   zeigen, 409 ist ein Stopp-Signal, kein Umgehungssignal.
9. Freigegebene Revisionen sind immutable; Aenderungen laufen immer ueber
   neue Revisionen mit change_reason.
10. Statusuebergaenge nur ueber die Transition-Endpoints; die erlaubte
    Matrix steht in der DB-Tabelle workflow_transitions.
11. Jeder schreibende Call fuehrt einen Grund (reason) mit.
12. Interne Daten (Kosten, Lieferanten) werden vom Agenten nicht in
    Extern-Reports aufgenommen; der Report-Filter laesst nur
    released-Inhalte zu.
