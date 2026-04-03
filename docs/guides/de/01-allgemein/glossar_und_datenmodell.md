# Glossar und Datenmodell

Dieses Dokument erklaert die wichtigsten Begriffe, Status und Beziehungen der App.

## Begriffe

- `TSE`
  Technische Sicherheitseinrichtung fuer rechtssichere Signierung von Kassenvorgaengen.
- `TSS`
  Technische Sicherheitseinrichtung im Provider-Modell, in der Clients und Transaktionen liegen.
- `TSE Security Device`
  Lokaler Doctype fuer die TSS.
- `TSE Client`
  Fiskaly-Client fuer ein POS Profile.
- `TSE Transaction`
  Signierte oder in Bearbeitung befindliche Transaktion fuer eine `POS Invoice`.
- `DSFinV-K Cash Register`
  DSFinV-K-Abbild des Kassenplatzes je Client.
- `DSFinV-K Cash Point Closing`
  DSFinV-K-Kassenabschluss auf Basis eines `POS Closing Entry`.
- `DSFinV-K Export`
  Exportjob fuer einen Zeitraum.

## Zentrale Beziehungen

```text
TSE Security Device
  -> TSE Client
    -> POS Profile
      -> POS Invoice
        -> TSE Transaction

TSE Client
  -> DSFinV-K Cash Register

POS Closing Entry
  -> DSFinV-K Cash Point Closing
    -> DSFinV-K Export
```

## Wichtige Status

### TSE Transaction

- `ACTIVE`
  bei Fiskaly gestartet, aber noch nicht sauber abgeschlossen
- `FINISHED`
  normaler erfolgreicher Abschluss
- `CANCELLED`
  kontrollierter Abbruch eines noch offenen Vorgangs
- `ERROR`
  lokaler oder technischer Fehlerzustand
- `ORPHANED`
  lokaler Datensatz ohne gueltigen Provider-Match

### DSFinV-K Cash Point Closing

- `PENDING`
  lokal angelegt, Providerprozess laeuft an
- `WORKING`
  Provider arbeitet noch
- `COMPLETED`
  Abschluss erfolgreich
- `ERROR`
  lokaler Datensatz existiert, Providerprozess ist fehlgeschlagen
- `DELETED`
  bewusst bereinigter Datensatz, lokal und beim Provider als geloescht markiert

## Idempotenz im Cash Point Closing

Zur Vermeidung doppelter Closings wird ein stabiler `source_hash` verwendet.

Der Hash basiert auf:
- `company`
- `pos_profile`
- `client_id`
- `business_date`
- sortierten POS-Invoice-IDs des `POS Closing Entry`

Damit kann die App denselben fachlichen Kassenabschluss erkennen, auch wenn technische Retries stattfinden.
