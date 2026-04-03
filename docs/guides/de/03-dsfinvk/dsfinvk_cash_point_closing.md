# DSFinV-K Cash Point Closing

## Ziel
Das DSFinV-K Cash Point Closing bildet den Kassenabschluss fuer einen Zeitraum ab. Der Abschluss wird fachlich aus einem `POS Closing Entry` abgeleitet.

## Voraussetzungen
- DSFinV-K Cash Register ist **ACTIVE**.
- POS Closing Entry enthaelt POS Invoices.
- Jede POS Invoice hat eine TSE Transaction im Status **FINISHED**.
- DSFinV-K VAT Rate und DSFinV-K Payment Type Mapping sind gepflegt.

## Ablauf im UI
1) Oeffne einen **POS Opening Entry** und erfasse Zahlungen.
2) Erstelle und submitte einen **POS Closing Entry**.
3) Der `POS Closing Entry` kann zunaechst auf `Queued` stehen, waehrend ERPNext die Rechnungen verarbeitet.
4) Erst wenn der `POS Closing Entry` den fachlichen Status `Submitted` erreicht, wird ein **DSFinV-K Cash Point Closing** erstellt.
5) Der Status wird automatisch aktualisiert (PENDING/WORKING/COMPLETED).

![DSFinV-K Cash Point Closing Liste](/docs/assets/DSFinV-K-Cash-Point-Closing/DSFinV-K_CASH_POINT_CLOSING.png)

![DSFinV-K Cash Point Closing Details](/docs/assets/DSFinV-K-Cash-Point-Closing/DSFinV-K_CASH_POINT_COSING_DETAILS.png)

## Was der Prozess macht
- Sammelt die POS Invoices aus dem Closing.
- Nutzt die TSE Transaction der POS Invoice (tss_tx_id, transaction_number).
- Erstellt die Cash Statement Payment-Block Daten aus der Closing Payment Reconciliation.
- Erstellt Transaction-Arrays inkl. VAT Breakdown und Payment Types.
- Setzt `business_date` auf `posting_date` des POS Closing Entry.
- Loggt Provider Events fuer jedes API-Call.

## Idempotenz und Deduplizierung

- Fuer jeden fachlichen Kassenabschluss wird ein `source_hash` aufgebaut.
- Der Hash basiert auf `company`, `pos_profile`, `client_id`, `business_date` und den sortierten POS-Invoice-IDs.
- Existiert bereits ein aktiver Datensatz mit demselben `source_hash`, wird kein zweites aktives Closing erzeugt.
- Manuelle Retries arbeiten auf demselben `ERROR`-Datensatz weiter.

## Wichtige Hinweise
- `transaction_export_id` ist der POS Invoice Name (BON_ID).
- `number` ist die TSE Transaction Number (BON_NR).
- Bei fehlendem Mapping oder fehlender TSE Transaction wird der Closing fehlschlagen.
- Der Status wird via Job auch spaeter nachgezogen, falls er noch PENDING ist.
- `DELETED` bedeutet bewusste administrative Bereinigung und kein lokales Hart-Loeschen.

## Fehler und Retry
- Falls der Create-Prozess fehlschlaegt, bleibt der Datensatz lokal erhalten und wechselt auf `ERROR`.
- Ein manueller Retry erfolgt ueber denselben Datensatz, nicht ueber einen neuen Hauptdatensatz.
- Details: `docs/guides/de/03-dsfinvk/dsfinvk_cash_point_closing_retry.md`
