# DSFinV-K Cash Point Closing

## Ziel
Das DSFinV-K Cash Point Closing bildet den Kassenabschluss fuer einen Zeitraum ab. Der Abschluss wird beim Submit eines POS Closing Entry erstellt.

## Voraussetzungen
- DSFinV-K Cash Register ist **ACTIVE**.
- POS Closing Entry enthaelt POS Invoices.
- Jede POS Invoice hat eine TSE Transaction im Status **FINISHED**.
- DSFinV-K VAT Rate und DSFinV-K Payment Type Mapping sind gepflegt.

## Ablauf im UI
1) Oeffne einen **POS Opening Entry** und erfasse Zahlungen.
2) Erstelle und submitte einen **POS Closing Entry**.
3) Beim Submit wird ein **DSFinV-K Cash Point Closing** erstellt.
4) Der Status wird automatisch aktualisiert (PENDING/WORKING/COMPLETED).

![DSFinV-K Cash Point Closing Liste](/docs/assets/DSFinV-K-Cash-Point-Closing/DSFinV-K_CASH_POINT_CLOSING.png)

![DSFinV-K Cash Point Closing Details](/docs/assets/DSFinV-K-Cash-Point-Closing/DSFinV-K_CASH_POINT_COSING_DETAILS.png)

## Was der Prozess macht
- Sammelt die POS Invoices aus dem Closing.
- Nutzt die TSE Transaction der POS Invoice (tss_tx_id, transaction_number).
- Erstellt die Cash Statement Payment-Block Daten aus der Closing Payment Reconciliation.
- Erstellt Transaction-Arrays inkl. VAT Breakdown und Payment Types.
- Setzt `business_date` auf `posting_date` des POS Closing Entry.
- Loggt Provider Events fuer jedes API-Call.

## Wichtige Hinweise
- `transaction_export_id` ist der POS Invoice Name (BON_ID).
- `number` ist die TSE Transaction Number (BON_NR).
- Bei fehlendem Mapping oder fehlender TSE Transaction wird der Closing fehlschlagen.
- Der Status wird via Job auch spaeter nachgezogen, falls er noch PENDING ist.
