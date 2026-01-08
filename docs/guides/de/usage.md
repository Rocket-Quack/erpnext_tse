<div align="center">
  <p>
    <img src="/docs/assets/TSE_APP_LOGO.png" alt="ERPNext TSE Logo" width="164"/>
  </p>
    <h1>TSE ERPNext taegliche Nutzung</h1>
</div>

Diese Anleitung beschreibt die Nutzung der TSE App im Betrieb und wie signierte POS Belege entstehen.

## Grundprinzip

- Beim Submit einer **POS Invoice** startet die App eine TSE-Transaktion, schreibt die Prozessdaten und beendet die Transaktion wieder.
- Die Signaturdaten (Signaturzaehler, Transaktionsnummer, QR-Daten) werden in der **TSE Transaction** gespeichert und in der **POS Invoice** verlinkt.
- Ob und wie die Daten auf dem Bon erscheinen, haengt vom Druckformat ab.

## Tagesablauf im POS

1. Pruefe, dass **TSE Settings** aktiviert sind.
2. Stelle sicher, dass der **TSE Client** im Status **REGISTERED** ist.
3. Oeffne den POS und waehle ein POS Profile mit verknuepftem TSE Client.
4. Erstelle eine POS Invoice und submitte sie.
5. Kontrolliere danach die verlinkte **TSE Transaction** und den Status **FINISHED**.

![TSE Transaction Beispiel](/docs/assets/TSE-Transaction/TSE_TRANSACTION.gif)

## Was regelmaessig geprueft werden sollte

- **TSE Security Device** steht auf **INITIALIZED**.
- **TSE Client** steht auf **REGISTERED**.
- In **TSE Transaction** tauchen keine **ERROR** oder **ORPHANED** Eintraege auf.
- Fehlerdetails stehen in den **Provider Events** der jeweiligen Doctypes.

## Typische Ursachen fuer Fehler

- Fehlende Zuordnung der **TSE Payment Types** (Mode of Payment -> CASH/NON_CASH).
- Fehlende Zuordnung der **TSE VAT Rates** zu Steuerkonten.
- Ungueltige oder abgelaufene fiskaly Tokens (Test TSE Auth in den TSE Settings).

## Tagesabschluss und DSFinV-K

- Beim Submit eines **POS Closing Entry** wird automatisch ein **DSFinV-K Cash Point Closing** erstellt.
- Der Status sollte nach Abschluss auf **COMPLETED** stehen.
- Fuer Exporte nutze den Doctype **DSFinV-K Export** und starte den Export manuell.

## Recovery (nur im Notfall)

Wenn lokale Daten und Provider-Daten auseinanderlaufen, aktiviere den **Recovery Modus** in den TSE Settings und nutze die Recovery Guides:

- `docs/guides/de/recovery_tse_security_device.md`
- `docs/guides/de/recovery_tse_client.md`
- `docs/guides/de/recovery_tse_transaction.md`
