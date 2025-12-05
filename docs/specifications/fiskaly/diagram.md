# Erstkonfiguration der Fiskaly-TSE

#TODO

# Ablauf POS-Rechnung 

```mermaid
sequenceDiagram
    participant User as POS User
    participant POS as ERPNext POS
    participant App as TSE App
    participant Fiskaly as Fiskaly API

    User->>POS: POS öffnen / POS Profile wählen
    POS->>App: Lade TSE Settings + TSE Client vom POS Profile
    App->>Fiskaly: Überprüfe Token / Aktualisiere Auth Token
    App->>App: Prüfe TSS-Status (REGISTERED/AKTIV)

    User->>POS: Beleg abschließen (Submit POS Invoice)

    POS->>App: on_submit(POS Invoice)
    App->>Fiskaly: START Transaction
    App->>Fiskaly: UPDATE Transaction (Process Data: Beträge, Steuern)
    App->>Fiskaly: FINISH Transaction
    Fiskaly-->>App: Signaturdaten, QR-Daten, Zeitstempel

    App->>POS: Schreibe TSE-Daten in POS Invoice + lege TSE Transaction an

````

# Clients für TSE anlegen
#TODO


# POS Profile verknüpfen
#TODO
