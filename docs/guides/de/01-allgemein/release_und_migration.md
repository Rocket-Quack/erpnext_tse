# Release und Migration

Dieses Runbook beschreibt den sicheren Ablauf fuer Updates der App auf Produktivsystemen.

## Vor dem Update

1. Release Notes und relevante Guides lesen:
   - `01-allgemein/rollen_und_rechte.md`
   - `01-allgemein/troubleshooting.md`
   - `04-recovery/recovery_runbook.md`
2. Backup sicherstellen:
   - Datenbank-Backup
   - Files-Backup
   - optional Snapshot der gesamten Bench/VM
3. Offene Stoerungen pruefen:
   - keine ungeklaerten `ACTIVE` TSE Transactions
   - keine ungeklaerten `ERROR` Cash Point Closings
   - keine laufenden oder haengenden Exporte
4. Wartungsfenster planen, wenn Worker/Processes neu gestartet werden muessen.

## Standardablauf

1. App-Code aktualisieren.
2. Abhaengigkeiten installieren, falls das Release dies erfordert.
3. Migration ausfuehren:

```bash
bench --site <site> migrate
```

4. Cache leeren:

```bash
bench --site <site> clear-cache
```

5. Falls noetig Assets neu bauen und Prozesse neu starten:

```bash
bench build
bench restart
```

## Was bei dieser App besonders geprueft werden muss

- Background Jobs laufen wieder sauber an.
- `POS Invoice.tse_transaction` bleibt technisch `read_only` und `no_copy`.
- `DSFinV-K Cash Point Closing` erstellt sich weiterhin erst nach erfolgreichem `POS Closing Entry.status == Submitted`.
- `Retry Create`, `Mark as Deleted`, `Refresh Status` und `Resolve ACTIVE` stehen nur den vorgesehenen Rollen zur Verfuegung.

## Smoke Tests nach dem Update

1. `TSE Settings` oeffnen und Authentifizierung pruefen.
2. Eine `POS Invoice` submitten:
   - `TSE Transaction` wird verlinkt
   - Status endet auf `FINISHED`
3. Einen `POS Closing Entry` submitten:
   - zunaechst ggf. `Queued`
   - danach genau ein `DSFinV-K Cash Point Closing`
4. Einen bestehenden `ERROR`-Cash-Point-Closing-Datensatz pruefen:
   - `Retry Create` sichtbar nur fuer Admin-Rollen
5. Einen bestehenden `COMPLETED`-Cash-Point-Closing-Datensatz pruefen:
   - `Mark as Deleted` sichtbar nur fuer Admin-Rollen

## Rollback-Grundsaetze

- Kein Rollback auf Dateiebene ohne konsistente Datenbankstrategie.
- Vor allem keine halb ausgefuehrte Migration mit altem Code weiterbetreiben.
- Wenn ein Release fachliche Daten veraendert hat, zuerst die Datenlage bewerten, dann erst Code zuruecksetzen.

## Bekannte betriebliche Grenzen

- Die App setzt fuer TSE und DSFinV-K praktisch Fiskaly voraus.
- Worker und Scheduler sind fuer Retry-, Status- und Export-Nachlaeufe notwendig.
- Bereits gezogene Exporte muessen vor spaeterem Cleanup fachlich neu bewertet werden.
