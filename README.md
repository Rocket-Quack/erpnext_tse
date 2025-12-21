<div align="center">
  <p>
    <img src="docs/assets/TSE_APP_LOGO.png" alt="ERPNext TSE Logo" width="164"/>
  </p>
    <h1>TSE ERPNext Integration</h1>
</div>


Diese App erweitert ERPNext um die Anbindung an eine Technische Sicherheitseinrichtung (TSE) und stellt die Grundlagen für gesetzeskonforme Kassenvorgänge in Deutschland bereit. 

Für die technische Umsetzung der TSE-Anbindung wird der Cloud-TSE-Anbieter [Fiskaly](https://www.fiskaly.com/) verwendet. Dadurch erfolgt die Verwaltung der TSE vollständig aus ERPNext heraus, während Fiskaly die gesetzeskonforme Signierung der Transaktionen gemäß KassenSichV übernimmt.

Somit ist es möglich Gesetzeskonform die POS-Oberfläche von ERPNext zu nutzen und hierbei die KassenSichV zu erfüllen.

## Supported Versions

| ERPNext | Frappe | Support-Status |
|---------|--------|----------------|
| v16 Beta    | v16 Beta   | ⚙️ Bald Verfügbar     |
| v15     | v15    | ✅ Unterstützt     |

## Installation (Frappe Cloud)

Die App kann direkt über die Frappe Cloud installiert werden:

1. Öffne das Frappe Cloud Dashboard unter <https://frappecloud.com/dashboard/#/sites>
2. Klicke auf **"New Site"**, um eine neue Instanz zu erstellen
3. Im Schritt **„Select apps to install“**:
   - Wähle die gewünschte Frappe-/ERPNext-Version aus  
   - Aktiviere zusätzlich die App **`ERPNEXT TSE`**
4. Schließlich den Assistenten abschließen bis die Seite erstellt wurde

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

### Print Format

Das Print Format "POS Invoice TSE" erweitert den Standard-POS-Beleg um die rechtlich relevanten TSE-Daten. Am Belegende wird ein QR-Code angezeigt, der aus dem Feld `qr_code_data` der verknüpften TSE-Transaktion erzeugt wird und die signierten Informationen enthält. 
Zusätzlich werden die in der TSE-Transaktion gespeicherten Daten ausgegeben:
- `transaction_id`
- `transaction_number`
- `signature_counter`
- `start_time`
- `end_time`

Dadurch sind sowohl der QR-Code als auch die zugehörigen Signatur- und Transaktionsdaten direkt auf dem Beleg.
Rechtlich gesehen reicht auch nur der QR-Code zur Anageb der TSE Transaktion.

## Support & Inbetriebnahme

### Community-Support (kostenlos)
- **Bug Reports & Feature Requests:** 
- **Fragen zur Allgemeinen Nutzung:**

Bitte über die [Issues](https://github.com/Rocket-Quack/erpnext_tse/issues) ein Ticket erstellen

### Erweiterte Unterstützung (optional / kommerziell)
Kommerzielle Unterstützung ist optional und richtet sich an besondere
Anforderungen oder komplexere Setups.  

In den meisten Fällen ist keine kommerzielle Unterstützung erforderlich.
Die App ist so konzipiert, dass Installation, Konfiguration und Betrieb
mit der bereitgestellten Dokumentation selbstständig leicht möglich sein sollte.

Für Unterstützung die dennoch gewünscht ist, z. B. bei:
- Installation, Inbetriebnahme und Konfiguration
- Troubleshooting in produktionsnahen Setups
- Anpassungen / Integrationen

können Anfragen über das Kontaktformular gestellt werden:  
🦆 [Quack Senden](https://rocket-quack.github.io/website/contact-erpnext-tse) 🦆

## Sponsoren ❤️

Die Entwicklung und Wartung wird durch Sponsoren und freiwillige Unterstützung ermöglicht. 

Ein besonderer Dank geht hierbei an die folgenden Unterstützer:

<a href="https://puzzles-shisha.de/" target=_blank><img
  src="https://puzzles-shisha.de/cdn/shop/files/Logo_Puzzles_2.png?v=1717513250&width=90" height="50"
/></a>

Wer das Projekt unterstützen möchte, kann dies gerne über
[Ko-fi](https://ko-fi.com/rocketquack) tun.


Hinweis: Sponsoren und Unterstützer haben keinen Einfluss auf Funktionalität, Roadmap oder Quellcode.

## License

Copyright (C) 2025 RocketQuackIT

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

GNU GPL V3. See the `LICENSE` file for more information.
