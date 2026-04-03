<div align="center">
  <p>
    <img src="/docs/assets/TSE_APP_LOGO.png" alt="ERPNext TSE Logo" width="164"/>
  </p>
    <h1>TSE ERPNext Erste Konfiguration</h1>
</div>

Diese Anleitung beschreibt die erste Konfiguration der TSE-App und eine Uebersicht der anzulegenden Daten.

## Voraussetzungen

- ERPNext TSE ist installiert.
- Du hast die Rolle **TSE Admin** oder **System Manager**.
- Ein aktiver **fiskaly-Account** mit TSE API Key/Secret (und optional DSFinV-K API Key/Secret) ist vorhanden.

## 1. TSE Settings einrichten

1. Oeffne **TSE Settings** (Suche in der ERPNext Leiste).
2. Aktiviere **Activated**.
3. Waehle **Cloud Provider = Fiskaly**.
4. Optional: Passe **Base URL** und **DSFinV-K Base URL** an, wenn du eigene Endpunkte nutzt.
5. Trage **TSE API Key** und **TSE API Secret** ein.
6. Optional: Trage **DSFinV-K API Key** und **DSFinV-K API Secret** ein, falls abweichend.
7. Speichere den Datensatz.

Hinweis: Fiskaly empfiehlt, pro Dienst (TSE und DSFinV-K) eigene API Keys zu verwenden. Daher sind die Zugangsdaten getrennt.

Nach dem Speichern erscheint der Button **Test TSE Auth**. Damit pruefst du die Verbindung zu fiskaly und siehst:
- **Organization ID**
- **Access Token Expires At**
- **Last Auth Status** und **Last Auth Message**

Optional kannst du **Test DSFinV-K Auth** nutzen, um die DSFinV-K Zugangsdaten separat zu pruefen.

![DSFinV-K Settings in TSE Settings](/docs/assets/DSFinV-K-Settings/DSFinV-K_SETTINGS.png)

## 2. TSE Security Device (TSS) anlegen

1. Erstelle einen neuen Datensatz **TSE Security Device**.
2. Vergib einen **Internal Name** und (optional) eine **Company**.
3. Speichere den Datensatz.
4. Nutze unter **TSE Actions** den Button **Create TSS at Provider**.
5. Speichere **Admin PUK** und **TSS ID** sicher. Diese Werte koennen nicht erneut abgerufen werden.
6. Fuehre anschliessend (je nach Status) **Deploy TSS at Provider** und **Initialize TSS at Provider** aus.

Zielstatus fuer den Betrieb ist **INITIALIZED**.

![TSE Security Device erstellen](/docs/assets/TSE-Security-Device/TSE_SECURITY_DEVICE_CREATE.gif)

## 3. TSE Client anlegen und POS Profile verknuepfen

1. Erstelle einen neuen Datensatz **TSE Client**.
2. Setze **Client Name**, **Company**, **TSE Security Device** (Status INITIALIZED) und ein **POS Profile**.
3. Speichere den Datensatz.
4. Klicke unter **TSE Client** auf **Create Client at Provider**.

Nach erfolgreicher Registrierung steht der Status auf **REGISTERED**. Bei Bedarf kannst du spaeter **Deregister** oder **Register** nutzen.

Hinweis: Beim Registrieren wird automatisch ein **DSFinV-K Cash Register** angelegt oder aktualisiert.

![TSE Client erstellen](/docs/assets/TSE-Client/TSE_CLIENT_CREATE.gif)

## 4. TSE Payment Types und VAT Rates

### TSE Payment Types
Ordne die vordefinierten Codes einem **Mode of Payment** zu:
- `CASH` fuer Barzahlungen
- `NON_CASH` fuer alle unbaren Zahlarten

Fehlende Zuordnungen fuehren zu Fehlern beim POS Abschluss.

### TSE VAT Rates
Ordne jedem Steuerkonto (Account Type = Tax) einen **VAT Rate Code** zu. Standardwerte werden bei der Installation angelegt, die Zuordnung zu deinen Konten musst du selbst setzen.

## 5. DSFinV-K Einstellungen

- **DSFinV-K Base URL** (optional) in den TSE Settings.
- **DSFinV-K API Key/Secret** (optional, falls abweichend von TSE).
- **Export Retention (Days)** steuert, wie lange heruntergeladene Exporte gespeichert bleiben.
- **DSFinV-K VAT Rate**: Tax Account -> VAT Definition ID.
- **DSFinV-K Payment Type**: Mode of Payment -> Payment Type (z. B. Bar, Unbar, ECKarte).
- **Cash Register** und **Cash Point Closing** werden automatisch im Client- und POS-Closing-Prozess angelegt.

![DSFinV-K Payment Types](/docs/assets/DSFinV-K-Settings/DSFinV-K_PAYMENT_TYPES.png)

![DSFinV-K VAT Rates](/docs/assets/DSFinV-K-Settings/DSFinV-K_VAT_RATES.png)

## 6. Testlauf

1. Erstelle eine **POS Invoice** und submitte sie.
2. Pruefe den Link zur **TSE Transaction** in der POS Invoice.
3. Stelle sicher, dass der Status der Transaktion **FINISHED** ist und Signaturdaten vorhanden sind.
4. Fuehre einen **POS Closing Entry** durch und pruefe den **DSFinV-K Cash Point Closing** Status.

## 7. Recovery und Debug (optional)

- **Recovery Modus** in den TSE Settings nur aktivieren, wenn Daten aus dem Provider neu abgeglichen werden muessen.
- Fuer Debugging kann **Enable Debug Logging** aktiviert werden. Verwende dies nur kurzfristig.

## Weiterfuehrende Guides

- Guide-Uebersicht: `docs/guides/de/README.md`
- Ablaufdiagramme: `docs/guides/de/01-allgemein/process_diagram.md`
- Taegliche Nutzung: `docs/guides/de/01-allgemein/usage.md`
- Glossar und Datenmodell: `docs/guides/de/01-allgemein/glossar_und_datenmodell.md`
- Troubleshooting: `docs/guides/de/01-allgemein/troubleshooting.md`
- TSE Fehlerbehandlung: `docs/guides/de/02-tse/tse_transaction_active_recovery.md`
- Recovery: `docs/guides/de/04-recovery/recovery_tse_security_device.md`, `docs/guides/de/04-recovery/recovery_tse_client.md`, `docs/guides/de/04-recovery/recovery_tse_transaction.md`
