# Recovery Runbook

Dieses Runbook beschreibt die sichere Reihenfolge fuer Recovery im Produktivbetrieb.

## Grundsatz

Recovery ist kein Routinebetrieb. Recovery wird nur genutzt, wenn lokale und Provider-Daten sichtbar auseinanderlaufen oder nach Stoerungen/Desaster-Szenarien Daten neu abgeglichen werden muessen.

## Vorbedingungen

- `Recovery Modus` ist bewusst aktiviert
- Fiskaly-Zugangsdaten sind gueltig
- Worker laufen
- ein verantwortlicher Admin begleitet den Vorgang

## Empfohlene Reihenfolge

1. `TSE Security Device`
2. `TSE Client`
3. `TSE Transaction`

Damit werden Abhaengigkeiten von oben nach unten wieder aufgebaut.

## Was Recovery ausdruecklich nicht ist

- kein Ersatz fuer `Resolve ACTIVE`
- kein Ersatz fuer `Retry Create`
- kein Werkzeug zum lokalen Hart-Loeschen

## Wann welches Werkzeug zu verwenden ist

- haengende `ACTIVE` TSE Transaction:
  `02-tse/tse_transaction_active_recovery.md`
- `DSFinV-K Cash Point Closing` auf `ERROR`:
  `03-dsfinvk/dsfinvk_cash_point_closing_retry.md`
- provider/lokal strukturell inkonsistent:
  Recovery-Sync nach dieser Reihenfolge

## Nachkontrollen

- Status der synchronisierten Datensaetze pruefen
- `Provider Events` und Fehlertexte pruefen
- pruefen, ob betroffene POS-Belege oder Closings weiterhin fachlich blockiert sind
