# ERPNext TSE Guides (DE)

Diese Uebersicht ist der Einstiegspunkt fuer Betrieb, Einrichtung und Stoerungsbehebung der ERPNext-TSE-App.

## Start Here

Wenn du die App neu einrichtest:
- `01-allgemein/installation.md`
- `01-allgemein/configuration.md`
- `01-allgemein/glossar_und_datenmodell.md`

Wenn du die App im Tagesbetrieb nutzt:
- `01-allgemein/usage.md`
- `01-allgemein/monitoring_und_betrieb.md`
- `03-dsfinvk/dsfinvk_cash_point_closing.md`

Wenn gerade ein Fehler vorliegt:
- `01-allgemein/troubleshooting.md`
- `02-tse/tse_transaction_active_recovery.md`
- `03-dsfinvk/dsfinvk_cash_point_closing_retry.md`
- `04-recovery/recovery_runbook.md`

Wenn ein Update fuer ein Produktivsystem ansteht:
- `01-allgemein/release_und_migration.md`
- `01-allgemein/rollen_und_rechte.md`

## 01 Allgemein

- `01-allgemein/installation.md`
  Installation der App in einer bestehenden Bench/Site.
- `01-allgemein/configuration.md`
  Erstkonfiguration von TSE Settings, TSS, Clients, Mappings und DSFinV-K.
- `01-allgemein/usage.md`
  Tagesbetrieb, Monatsende und wichtigste Sichtpruefungen.
- `01-allgemein/process_diagram.md`
  Uebersicht der zentralen Prozessablaeufe.
- `01-allgemein/troubleshooting.md`
  Symptomorientiertes Runbook fuer die haeufigsten Betriebsfehler.
- `01-allgemein/release_und_migration.md`
  Release-, Migrations- und Rollback-Checkliste fuer Produktivsysteme.
- `01-allgemein/rollen_und_rechte.md`
  Welche Rollen welche administrativen Aktionen ausfuehren duerfen.
- `01-allgemein/monitoring_und_betrieb.md`
  Regelmaessige Betriebspruefungen fuer Worker, Scheduler und fachliche Status.
- `01-allgemein/glossar_und_datenmodell.md`
  Begriffe, Status und Beziehungen der wichtigsten Doctypes.

## 02 TSE

- `02-tse/tse_transaction_active_recovery.md`
  Fehlerbehandlung fuer haengende `ACTIVE`-Transaktionen und Admin-Reparatur.

## 03 DSFinV-K

- `03-dsfinvk/dsfinvk_cash_register.md`
  Cash Register und Beziehung zum TSE Client.
- `03-dsfinvk/dsfinvk_cash_point_closing.md`
  Erzeugung, Status und Idempotenz des Cash Point Closing.
- `03-dsfinvk/dsfinvk_cash_point_closing_retry.md`
  Retry-, Cleanup- und Fehlerbehandlung fuer Cash Point Closings.
- `03-dsfinvk/dsfinvk_export.md`
  Erstellung, Download und Grenzen des DSFinV-K Exports.

## 04 Recovery

- `04-recovery/recovery_runbook.md`
  Reihenfolge und Sicherheitsregeln fuer Recovery im Produktivbetrieb.
- `04-recovery/recovery_tse_security_device.md`
  Recovery-Sync fuer TSE Security Devices.
- `04-recovery/recovery_tse_client.md`
  Recovery-Sync fuer TSE Clients.
- `04-recovery/recovery_tse_transaction.md`
  Recovery-Sync fuer TSE Transactions.
