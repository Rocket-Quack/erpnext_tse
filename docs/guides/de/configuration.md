<div align="center">
  <p>
    <img src="/docs/assets/TSE_APP_LOGO.png" alt="ERPNext TSE Logo" width="164"/>
  </p>
    <h1>TSE ERPNext Erste Konfiguration</h1>
</div>

Diese Anleitung beschreibt die erste Konfiguration der TSE-App und eine Übersicht der anzulegenden Daten.

## Voraussetzungen

Für die Nutzung der Frappe App **ERPNext TSE** ist ein aktiver **fiskaly-Account** erforderlich.  
Die App kommuniziert direkt mit der fiskaly-API, um die Technische Sicherheitseinrichtung (TSE) gesetzeskonform zu verwalten. Ohne gültige fiskaly-Zugangsdaten (API Key und API Secret) ist keine Inbetriebnahme oder Nutzung der TSE möglich.

## API Key und API Secret bei fiskaly erstellen

**Hinweis:** Die Benutzeroberfläche kann sich ändern. Die folgenden Schritte beschreiben den üblichen und offiziellen Weg im fiskaly-Dashboard

### 1. Anmeldung im fiskaly Dashboard
- Rufe das [fiskaly Dashboard](https://dashboard.fiskaly.com/) auf.
- Melde dich mit deinem fiskaly-Benutzerkonto an oder erstelle bei Bedarf eines

### 2. Bereich „API Keys“ öffnen
- Navigiere im Dashboard zum Bereich **API Keys** bzw. **Developer / API-Zugänge**

<img src="/docs/assets/Fiskaly/Fiskaly_Settings_Sidebar.png" alt="Fiskaly Settings Sidebar"/>

### 3. Neuen API Key erstellen
- Klicke auf **Create API Key** / **Neuen API Key anlegen**
- Vergib einen aussagekräftigen Namen (z. B. `erpnext-tse`)

### 4. API Secret sicher speichern
- Nach dem Anlegen wird das **API Secret** einmalig angezeigt
- Kopiere das API Secret und speichere es sicher ab
- **Wichtig:** Das Secret kann später nicht erneut angezeigt werden. Bei Verlust muss ein neuer API Key erstellt werden

### 5. Zugangsdaten in ERPNext hinterlegen
- Trage den **API Key** und das **API Secret** in den Einstellungen der Frappe App **ERPNext TSE** ein

<img src="/docs/assets/TSE-Settings/API_KEY_API_SECRET.png" alt="ERPNext TSE Settings Ansicht"/>

## DSFinV-K Einstellungen

Die DSFinV-K Funktionen verwenden zusaetzliche Einstellungen und Mapping-Doctypes.

### 1. DSFinV-K Base URL (optional)
- In **TSE Settings** kann die DSFinV-K Base URL ueberschrieben werden.
- Standard: `https://dsfinvk.fiskaly.com/api/v1`

### 2. Export Retention (Days)
- In **TSE Settings** kann festgelegt werden, wie lange heruntergeladene Exportdateien gespeichert bleiben.
- Wert `0` deaktiviert die automatische Bereinigung.

### 3. DSFinV-K VAT Rate Mapping
- Doctype: **DSFinV-K VAT Rate**
- Jeder Tax Account muss einer VAT Definition ID zugeordnet werden.

### 4. DSFinV-K Payment Type Mapping
- Doctype: **DSFinV-K Payment Type**
- Jede Mode of Payment wird einem DSFinV-K Payment Type zugeordnet (Bar, Unbar, EC, Kreditkarte, ...).

### 5. DSFinV-K Cash Register und Cash Point Closing
- Cash Register werden automatisch beim Registrieren des TSE Clients angelegt.
- Cash Point Closings werden beim Submit eines POS Closing Entry erstellt.

### 6. DSFinV-K Export
- Exporte werden manuell im Doctype **DSFinV-K Export** gestartet.
- Format (zip/tar) wird beim Triggern angegeben.
