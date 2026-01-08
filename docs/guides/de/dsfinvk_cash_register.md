# DSFinV-K Cash Register

## Ziel
Das DSFinV-K Cash Register bildet die Kasse fuer die DSFinV-K Schnittstelle ab. Es wird automatisch erstellt, sobald ein TSE Client bei Fiskaly registriert wird.

## Voraussetzungen
- TSE Settings: aktiviert, Fiskaly Zugangsdaten gesetzt.
- TSE Client ist mit einem POS Profile verknuepft.
- Company hat eine Default Currency.

## Ablauf im UI
1) Erstelle oder oeffne einen **TSE Client**.
2) Klicke auf **Create Client at Provider** (Client registrieren).
3) Das DSFinV-K Cash Register wird im Hintergrund angelegt/aktualisiert.
4) Der Status erscheint im Doctype **DSFinV-K Cash Register**.

![DSFinV-K Cash Register](/docs/assets/DSFinV-K-Cash-Register/DSFinV-K_CASH_REGISTER.png)

## Was der Prozess macht
- Cash Register wird mit der `client_id` des TSE Clients angelegt (1:1 Beziehung).
- Brand/Model/Software werden gesetzt (ERPNext, POS Profile/Client Name).
- Base Currency wird aus der Company uebernommen.
- Status wird aktualisiert (ACTIVE/ERROR).
- Provider Events werden protokolliert.

## Wichtige Hinweise
- Kein manueller Button am Cash Register noetig (automatisch im Client-Prozess).
- Bei Fehlern wird der Status auf **ERROR** gesetzt und ein Provider Event geschrieben.
- Aenderungen am POS Profile oder an der Company Currency erfordern ein erneutes Upsert.
