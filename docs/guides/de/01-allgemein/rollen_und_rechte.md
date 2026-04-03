# Rollen und Rechte

Dieses Dokument beschreibt die praktische Rollenverteilung fuer Betrieb und Support.

## Standardrollen

- `System Manager`
  Vollzugriff auf Einrichtung, Betrieb, Recovery und administrative Reparatur.
- `TSE Admin`
  Operativer Admin fuer TSE- und DSFinV-K-bezogene Prozesse.

## Typische Admin-Aktionen

`System Manager` und `TSE Admin` duerfen:
- `TSE Settings` konfigurieren und Auth testen
- `TSE Security Device` und `TSE Client` verwalten
- Recovery-Syncs anstossen
- `TSE Transaction`:
  - `Refresh Status`
  - `Resolve ACTIVE`
- `DSFinV-K Cash Point Closing`:
  - `Retry Create`
  - `Mark as Deleted`
- `DSFinV-K Export` erstellen und herunterladen

## Sichtbarkeit im UI

Einige Schaltflaechen sind absichtlich nur fuer Admin-Rollen sichtbar, damit normale Nutzer nicht mit technischen Reparaturaktionen konfrontiert werden.

Dazu gehoeren insbesondere:
- `Resolve ACTIVE`
- `Retry Create`
- `Mark as Deleted`

Die serverseitige Rechtepruefung bleibt auch dann aktiv, wenn jemand einen direkten RPC-Aufruf versuchen sollte.

## Empfehlung fuer produktive Rollenvergabe

- `System Manager`
  nur fuer technische Administratoren und Release-Verantwortliche
- `TSE Admin`
  fuer operative Kassen-/Support-Verantwortliche
- normale POS-Nutzer
  keine technischen TSE-Reparaturaktionen

## Wann zusaetzliche Freigabe sinnvoll ist

Vor folgenden Aktionen sollte intern ein Vier-Augen-Prinzip gelten:
- `Mark as Deleted` auf `DSFinV-K Cash Point Closing`
- Recovery-Sync in Produktivsystemen
- manuelle Bereinigung haengender `ACTIVE`-Transaktionen
- produktive Updates und Migrationen
