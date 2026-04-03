# Erstkonfiguration der Fiskaly-TSE

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant ERP as ERPNext TSE
    participant Fiskaly as Fiskaly Dashboard/API

    Admin->>Fiskaly: API-Key und Secret erstellen
    Admin->>ERP: API-Key/Secret in TSE Settings eintragen
    ERP->>Fiskaly: Authentifizieren und Token abrufen
    ERP->>Fiskaly: TSS anlegen (Security Device)
    Fiskaly-->>ERP: TSS-ID und Status
    ERP->>ERP: Einstellungen speichern + Security-Device-Datensatz anlegen
    Admin->>ERP: Status pruefen = REGISTERED/ACTIVE
```

# Ablauf POS-Rechnung

```mermaid
sequenceDiagram
    participant User as POS User
    participant POS as ERPNext POS
    participant App as TSE App
    participant Fiskaly as Fiskaly API

    User->>POS: POS oeffnen / POS Profile waehlen
    POS->>App: Lade TSE Settings + TSE Client vom POS Profile
    App->>Fiskaly: Ueberpruefe Token / aktualisiere Auth Token
    App->>App: Pruefe TSS-Status (REGISTERED/AKTIV)

    User->>POS: Beleg abschliessen (Submit POS Invoice)

    POS->>App: on_submit(POS Invoice)
    App->>Fiskaly: START Transaction
    App->>Fiskaly: UPDATE Transaction (Process Data: Betraege, Steuern)
    App->>Fiskaly: FINISH Transaction
    Fiskaly-->>App: Signaturdaten, QR-Daten, Zeitstempel

    App->>POS: Schreibe TSE-Daten in POS Invoice + lege TSE Transaction an
```

# Clients fuer TSE anlegen

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant ERP as ERPNext TSE
    participant Fiskaly as Fiskaly API

    Admin->>ERP: Neuen TSE Client anlegen
    ERP->>ERP: TSS-Status pruefen (REGISTERED/ACTIVE)
    ERP->>Fiskaly: Client registrieren (tss_id, client_id)
    Fiskaly-->>ERP: Client-ID und Status
    ERP->>ERP: Client-Datensatz speichern
```

# POS Profile verknuepfen

Kurzbeschreibung:
- POS Profile fachlich zuerst anlegen.
- Im TSE Client das passende POS Profile auswaehlen und speichern.
- Die Verknuepfung ist notwendig, damit Verkaeufe signiert werden koennen.

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant POS as ERPNext POS Profile
    participant Client as TSE Client
    participant ERP as ERPNext TSE

    Admin->>POS: POS Profile anlegen
    Admin->>Client: TSE Client oeffnen
    Client->>ERP: Liste verfuegbarer POS Profile laden
    Admin->>Client: POS Profile auswaehlen
    Client->>ERP: Verknuepfung speichern
    ERP->>Client: Bestaetigung und Status anzeigen
```

# Recovery-Sync fuer Security Devices (TSE)

Kurzbeschreibung:
- In **TSE Settings** den Schalter **Recovery Modus** aktivieren.
- In der Liste **TSE Security Device** den Button **Recovery Sync** starten (nur im Recovery Modus sichtbar).
- Meldungen: "Recovery sync queued (Job ID: ...)" beim Start, danach "Recovery sync completed successfully."
- Abgleich der TSS: lokale Eintraege aktualisieren/neu anlegen, nicht gefundene auf `ORPHANED` setzen.
- Fehlt ein Admin PUK, erscheint der Dialog **Missing Admin PUKs** mit Aktion **Save PUKs**.

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant ERP as ERPNext TSE
    participant Fiskaly as Fiskaly API

    Admin->>ERP: "Recovery Modus" in TSE Settings aktivieren
    Admin->>ERP: Liste "TSE Security Device" -> "Recovery Sync"
    ERP-->>Admin: "Recovery sync queued (Job ID: ...)"
    ERP->>Fiskaly: TSS Liste abrufen
    ERP->>ERP: Abgleichen/aktualisieren/anlegen/orphaned setzen
    ERP-->>Admin: "Recovery sync completed successfully."
    ERP->>Admin: Dialog "Missing Admin PUKs" (falls noetig)
    Admin->>ERP: "Save PUKs"
```

# Recovery-Sync fuer TSE Clients

Kurzbeschreibung:
- In **TSE Settings** den Schalter **Recovery Modus** aktivieren.
- In der Liste **TSE Client** den Button **Recovery Sync** starten (nur im Recovery Modus sichtbar).
- Meldung nach Abschluss: "Recovery sync completed successfully."
- Abgleich der Clients je TSS: lokal matchen, aktualisieren/neu anlegen, fehlende auf `ORPHANED` setzen.

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant ERP as ERPNext TSE
    participant Fiskaly as Fiskaly API

    Admin->>ERP: "Recovery Modus" in TSE Settings aktivieren
    Admin->>ERP: Liste "TSE Client" -> "Recovery Sync"
    ERP-->>Admin: "Recovery sync queued (Job ID: ...)"
    ERP->>Fiskaly: Clients je TSS abrufen
    ERP->>ERP: Abgleichen/aktualisieren/anlegen/orphaned setzen
    ERP-->>Admin: "Recovery sync completed successfully."
```

# Recovery-Sync fuer TSE Transaktionen

Kurzbeschreibung:
- In **TSE Settings** den Schalter **Recovery Modus** aktivieren.
- In der Liste **TSE Transaction** den Button **Recovery Sync** starten (nur im Recovery Modus sichtbar).
- Meldung nach Abschluss: "Recovery sync completed successfully."
- Abgleich der Transaktionen je TSS: lokal matchen, aktualisieren/neu anlegen, fehlende auf `ORPHANED` setzen.
- Empfehlung: erst TSE Clients recovern, damit Client-Links korrekt gesetzt werden koennen.

```mermaid
sequenceDiagram
    participant Admin as Administrator
    participant ERP as ERPNext TSE
    participant Fiskaly as Fiskaly API

    Admin->>ERP: "Recovery Modus" in TSE Settings aktivieren
    Admin->>ERP: Liste "TSE Transaction" -> "Recovery Sync"
    ERP-->>Admin: "Recovery sync queued (Job ID: ...)"
    ERP->>Fiskaly: Transaktionen je TSS abrufen
    ERP->>ERP: Abgleichen/aktualisieren/anlegen/orphaned setzen
    ERP-->>Admin: "Recovery sync completed successfully."
```
