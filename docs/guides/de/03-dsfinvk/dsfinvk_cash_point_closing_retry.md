# DSFinV-K Cash Point Closing: Fehler und Retry

## Ziel
Diese Anleitung beschreibt, wie mit `DSFinV-K Cash Point Closing` Datensaetzen im Status `ERROR` umzugehen ist und wie der manuelle Retry-Prozess funktioniert.

## Grundprinzip
- Der fachliche Datensatz fuer das Cash Point Closing wird bereits lokal angelegt, bevor der Provider-Create abgeschlossen ist.
- Wenn der Provider-Call oder ein nachgelagerter Verarbeitungsschritt fehlschlaegt, bleibt der Datensatz lokal erhalten und wird auf `ERROR` gesetzt.
- Ein erneuter Versuch wird nicht ueber den alten RQ-Job gestartet, sondern ueber den fachlichen Datensatz selbst.

## Wann ein Retry sinnvoll ist
Ein manueller Retry ist sinnvoll, wenn die Ursache temporaer oder bereits behoben ist, zum Beispiel:
- kurzzeitiger Provider- oder Netzwerkfehler
- behobenes Mapping-Problem
- voruebergehender Worker-/Verarbeitungsfehler

Kein Retry ohne Pruefung, wenn:
- das `POS Closing Entry` nicht mehr `Submitted` ist
- bereits ein anderes aktives Cash Point Closing fuer denselben fachlichen Inhalt existiert

## Entscheidungshilfe

- `ERROR` nach temporaerem Provider-/Worker-Fehler:
  Ursache pruefen, dann `Retry Create`
- `ERROR` wegen fachlichem Mapping-Problem:
  zuerst Mapping/Daten korrigieren, dann `Retry Create`
- doppelter oder fachlich falscher Datensatz:
  nicht retryen, sondern falschen Datensatz mit `Mark as Deleted` bereinigen

## Ablauf im UI
1. Oeffne den Datensatz **DSFinV-K Cash Point Closing**.
2. Pruefe den Status und die Provider Events.
3. Steht der Datensatz auf `ERROR`, erscheint fuer `TSE Admin` und `System Manager` der Button **Retry Create**.
4. Der Button queued einen neuen fachlichen Erzeugungsversuch.

## Verhalten des Retry
- Der bestehende `ERROR`-Datensatz wird wiederverwendet.
- Es wird kein zusaetzlicher Hauptdatensatz fuer denselben Fall erstellt.
- Bei Erfolg wird derselbe Datensatz auf `PENDING`, `WORKING` oder `COMPLETED` aktualisiert.
- Bei Bedarf wird ein vorhandener Provider-Datensatz zuerst synchronisiert, bevor ein neuer Create-Versuch gestartet wird.

## Mark as Deleted

`Mark as Deleted` ist fuer `System Manager` und `TSE Admin` gedacht, wenn ein Cash Point Closing fachlich falsch oder doppelt ist.

Dabei gilt:
- kein lokales Hart-Loeschen
- Provider-Delete bei Fiskaly wird ausgefuehrt
- lokal wechselt der Datensatz nur dann auf `DELETED`, wenn Fiskaly dies bestaetigt
- `cleanup_reason` ist Pflicht
- `Valid Record` ist optional und dokumentiert, welcher andere Datensatz gueltig bleiben soll

## Event-Log
Fuer den Retry werden zusaetzliche Events geschrieben:
- `RETRY_QUEUED`
- `RETRY_STARTED`
- `RETRY_SYNC_EXISTING`

Damit bleibt nachvollziehbar:
- wann ein Fehler auftrat
- wann ein Retry eingeleitet wurde
- ob nur synchronisiert oder wirklich neu erzeugt wurde

## Wichtige Hinweise
- Der Retry setzt voraus, dass das verknuepfte `POS Closing Entry` weiterhin submitted und fachlich gueltig ist.
- Der alte RQ-Job selbst wird nicht neu gestartet.
- Der Retry arbeitet am fachlichen Datensatz und ist deshalb langlebiger und nachvollziehbarer als ein reiner Queue-Retry.
- Bereits gezogene Exporte fuer denselben Zeitraum muessen vor einem spaeteren Cleanup fachlich geprueft werden.
