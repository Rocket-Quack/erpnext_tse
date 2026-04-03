# Monitoring und Betrieb

Dieses Dokument beschreibt die regelmaessigen Pruefungen fuer einen stabilen Betrieb.

## Taegliche Pruefungen

- `TSE Security Device` steht auf `INITIALIZED`
- `TSE Client` steht auf `REGISTERED`
- neue `TSE Transaction` Eintraege enden auf `FINISHED`
- neue `DSFinV-K Cash Point Closing` Eintraege enden auf `COMPLETED`

## Woechentliche Pruefungen

- keine offenen `ACTIVE` TSE Transactions ohne bekannte Ursache
- keine `ERROR` Cash Point Closings ohne Bearbeitungsstand
- keine dauerhaft `PENDING` oder `WORKING` Exporte
- Provider Events enthalten keine wiederkehrenden Auth- oder Mapping-Fehler

## Monatliche Pruefungen

1. Liste `TSE Transaction` nach `ACTIVE`, `ERROR`, `ORPHANED`
2. Liste `DSFinV-K Cash Point Closing` nach `ERROR`, `DELETED`
3. Liste `DSFinV-K Export` nach fehlgeschlagenen oder haengenden Jobs
4. Worker/Scheduler-Logs auf wiederkehrende Fehler pruefen

## Betriebskennzeichen fuer stoerungsfreien Zustand

- keine ungeklaerten `ACTIVE`-Transaktionen
- keine ungeklaerten `ERROR`-Closings
- keine ueberfaelligen Retry- oder Cleanup-Faelle
- Authentifizierung gegen Fiskaly erfolgreich

## Worker und Queue

Folgende Prozesse sind fuer den Betrieb relevant:
- Worker fuer Background Jobs
- Scheduler fuer periodische Nachlaeufe

Wenn Background Jobs nicht laufen, zeigen sich die Probleme typischerweise so:
- Cash Point Closings bleiben aus oder haengen
- Exporte wechseln nicht weiter
- Recovery-Syncs laufen nicht an

## Wann manuell eingegriffen werden sollte

- `TSE Transaction` bleibt auf `ACTIVE`
  - `Refresh Status`, danach ggf. `Resolve ACTIVE`
- `DSFinV-K Cash Point Closing` steht auf `ERROR`
  - Ursache pruefen, danach `Retry Create`
- doppeltes oder fachlich falsches `DSFinV-K Cash Point Closing`
  - mit `Mark as Deleted` sauber auf `DELETED` setzen

## Was nicht in den Routinebetrieb gehoert

- Recovery-Modus dauerhaft eingeschaltet lassen
- technische Link-Felder manuell pflegen
- fehlerhafte Datensaetze lokal hart loeschen
