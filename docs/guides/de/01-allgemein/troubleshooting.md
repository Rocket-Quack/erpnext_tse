# Troubleshooting

Dieses Runbook ordnet typische Symptome den wahrscheinlichsten Ursachen und den naechsten sinnvollen Schritten zu.

## Vor jeder Detailanalyse

1. Pruefe, ob `TSE Settings` aktiviert sind und die Authentifizierung erfolgreich ist.
2. Pruefe, ob Worker und Scheduler laufen.
3. Pruefe den Status der betroffenen Hauptobjekte:
   - `TSE Security Device`
   - `TSE Client`
   - `TSE Transaction`
   - `DSFinV-K Cash Point Closing`
4. Pruefe die `Provider Events` und den letzten Fehlertext im betroffenen Datensatz.

## Symptom: POS Invoice bleibt Draft

Wahrscheinliche Ursachen:
- TSE-Transaktion konnte nicht sauber gestartet oder beendet werden.
- Eine TSE-Transaktion haengt bei Fiskaly auf `ACTIVE`.
- Mappings fuer Zahlungsart oder Steuer fehlen.

Pruefe:
- Feld `POS Invoice.tse_transaction`
- verlinkte `TSE Transaction`
- Status `transaction_status`
- Provider Events der `TSE Transaction`

Naechste Aktion:
- bei `ACTIVE`: `02-tse/tse_transaction_active_recovery.md`
- bei `ERROR`: Provider Events und Mappings pruefen
- bei fehlendem Mapping: `01-allgemein/configuration.md`

## Symptom: TSE Transaction steht auf ACTIVE

Bedeutung:
- der normale Checkout wurde zwischen `start_transaction` und `finish_transaction` unterbrochen
- der Zustand blockiert moeglicherweise weitere fachliche Schritte

Pruefe:
- ist die verknuepfte `POS Invoice` noch Draft oder bereits submitted
- was meldet `Refresh Status`

Naechste Aktion:
- wenn die POS Invoice noch nicht submitted ist: `Resolve ACTIVE`
- wenn die POS Invoice bereits submitted ist: nicht blind canceln, zuerst Status synchronisieren
- Details: `02-tse/tse_transaction_active_recovery.md`

## Symptom: DSFinV-K Cash Point Closing wurde nicht erstellt

Wahrscheinliche Ursachen:
- `POS Closing Entry` ist noch `Queued`
- `POS Closing Entry` ist auf `Failed` gelaufen
- Worker hat den Background Job nicht verarbeitet
- ein aktives Duplikat wurde durch `source_hash` erkannt

Pruefe:
- `POS Closing Entry.docstatus`
- `POS Closing Entry.status`
- Worker/Queue
- vorhandene `DSFinV-K Cash Point Closing` Eintraege fuer denselben Tag/dasselbe Closing

Naechste Aktion:
- bei `Queued`: abwarten oder Worker pruefen
- bei `Failed`: fachliche Ursache im POS Closing loesen
- bei Duplikat: vorhandenen Datensatz verwenden, keinen manuellen Doppel-Create erzwingen

## Symptom: DSFinV-K Cash Point Closing steht auf ERROR

Bedeutung:
- der lokale Datensatz wurde bereits angelegt
- der Provider-Create oder ein nachgelagerter Verarbeitungsschritt ist fehlgeschlagen

Pruefe:
- Fehlertext im Datensatz
- `Provider Events`
- Mappings fuer `DSFinV-K VAT Rate` und `DSFinV-K Payment Type`
- Status des verknuepften `POS Closing Entry`

Naechste Aktion:
- temporaerer Fehler: `Retry Create`
- fachlicher Fehler: Ursache beheben und danach `Retry Create`
- Details: `03-dsfinvk/dsfinvk_cash_point_closing_retry.md`

## Symptom: Doppeltes DSFinV-K Cash Point Closing

Wahrscheinliche Ursachen:
- historischer Datensatz aus alter Prozesslogik
- manueller oder mehrfacher Nachlauf vor dem aktuellen Idempotenzschutz

Pruefe:
- `source_hash`
- `POS Closing Entry`
- `business_date`
- `client_id`
- Status aller beteiligten Closings

Naechste Aktion:
- genau einen gueltigen Datensatz behalten
- falsche doppelte Datensaetze nur ueber `Mark as Deleted` bereinigen
- nie lokal hart loeschen

## Symptom: DSFinV-K Export bleibt auf WORKING oder liefert falschen Zeitraum

Pruefe:
- Export-Filter (`Business Date` vs. `Creation Date`)
- Status der beteiligten Cash Point Closings
- ob relevante Closings auf `DELETED` gesetzt wurden

Naechste Aktion:
- Exportstatus refreshen
- Zeitraum und Filter pruefen
- bei bereits gezogenen Exporten fuer bereinigte Zeitraeume fachlich erneut pruefen

## Symptom: Recovery-Sync liefert unerwartete Daten

Pruefe:
- `Recovery Modus` ist wirklich bewusst aktiviert
- zuerst `TSE Security Device` und `TSE Client` synchronisieren
- erst danach `TSE Transaction`

Naechste Aktion:
- `04-recovery/recovery_runbook.md`

## Wann nicht automatisch weiterarbeiten

Nicht automatisch retryen oder loeschen, wenn:
- die fachliche Ursache unbekannt ist
- die verknuepfte `POS Invoice` oder das `POS Closing Entry` bereits submitted, aber fachlich unklar ist
- fuer den betroffenen Zeitraum bereits Exporte gezogen oder weitergegeben wurden
- Remote- und Lokalstatus sichtbar auseinanderlaufen
