<div align="center">
  <p>
    <img src="docs/assets/TSE_APP_LOGO.png" alt="ERPNext TSE Logo" width="164"/>
  </p>
    <h1>TSE ERPNext Integration</h1>
</div>


Diese App erweitert ERPNext um die Anbindung an eine Technische Sicherheitseinrichtung (TSE) und stellt die Grundlagen für gesetzeskonforme Kassenvorgänge in Deutschland bereit. 

Für die technische Umsetzung der TSE-Anbindung wird der Cloud-TSE-Anbieter [Fiskaly](https://www.fiskaly.com/) verwendet. Dadurch erfolgt die Verwaltung der TSE vollständig aus ERPNext heraus, während Fiskaly die gesetzeskonforme Signierung der Transaktionen gemäß KassenSichV übernimmt.

Somit ist es möglich Gesetzeskonform die POS-Oberfläche von ERPNext zu nutzen und hierbei die KassenSichV zu erfüllen.

## Installation (Frappe Cloud)

Die App kann direkt über die Frappe Cloud installiert werden:

1. Öffne das Frappe Cloud Dashboard unter <https://frappecloud.com/dashboard/#/sites>
2. Klicke auf **"New Site"**, um eine neue Instanz zu erstellen
3. Im Schritt **„Select apps to install“**:
   - Wähle die gewünschte Frappe-/ERPNext-Version aus  
   - Aktiviere zusätzlich die App **`ERPNEXT TSE`**
4. Schließe den Assistenten ab bis die Seite erstellt wurde

## Installation (Self-Hosted)

Sobald ERPNext installiert ist wird die App mittels des folgenden Befehl zur Bench Umgebung hinzugefügt.

```bash
bench get-app https://github.com/Rocket-Quack/erpnext_tse.git --branch version-15
```

Anschließend kann die App für eine Seite installiert werden.
```bash
bench --site yoursite.com install-app erpnext_tse
```


## Kurz-Anleitungen

Detaillierte Anleitungen finden Sie hier:
- [TSE ERPNext Integration installieren](/docs/guides/de/installation.md)
- [Erstkonfiguration TSE in ERPNext](/docs/guides/de/configuration.md)
- [Nutzung der TSE in Produktion](/docs/guides/de/usage.md)

Diese Kurzübersciht zeigt, wie Sie die TSE-APP in ERPNext nutzen.

### Allgemeine Konfiguration
#TODO

### TSE Konfigurationen

In diesem Schritt wird die eigentliche TSE Security Device angelegt.  
Auf dieser TSE werden später die einzelnen Kassen-Clients ihre elektronischen Transaktionen buchen.

<p>
  <img src="docs/assets/TSE-Security-Device/TSE_Full_Workflow.gif" alt="ERPNext Kompletter Workflow zum anlegen einer TSE"/>
</p>

Damit wird die komplette Lebensdauer der TSE von der Erstellung bis zur Deaktivierung direkt aus ERPNext heraus gesteuert.  
Es ist hierbei keine manuelle Pflege in Fiskaly nötig.

Zusätzlich werden alle Status-Änderungen zur Einsicht des Nutzers Dokumentiert und in einem eigenen Provider Response Protokoll gespeichert.

<p>
  <img src="docs/assets/TSE-Security-Device/TSE_Provider_Response.png" alt="Komplette Protokolierte Kommunikation mit Fiskaly in ERPNext gespeichert"/>
</p>

### POS-Profile Einstellungen
#TODO

### Signierte POS-Belege
#TODO

## License
GNU GPL V3. See the `LICENSE` file for more information.

## Sponsors
#TODO
