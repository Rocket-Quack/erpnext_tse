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