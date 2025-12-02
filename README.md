<p align="center">
  <img
    src="docs/assets/TSE_KEY_Logo.svg"
    alt="ERPNext TSE Logo"
    width="64"
  />
</p>

# ERPNext TSE Integration

## Übersicht
ERPNext TSE erweitert ERPNext um die Anbindung an eine Technische Sicherheitseinrichtung (TSE) und stellt die Grundlagen für gesetzeskonforme Kassenvorgänge in Deutschland bereit.

#TODO Fiskaly Umsetzung und Erklärung

## Installation

Sobald ERPNext installiert ist wird die App mittels des folgenden Befehl zur Bench Umgebung hinzugefügt.

```bash
bench get-app https://github.com/Rocket-Quack/erpnext_tse.git --branch version-15
```

Anschließend kann die App für eine Seite installiert werden.
```bash
bench --site yoursite.com install-app erpnext_tse
```

## Konfiguration
#TODO

## License
GNU GPL V3. See the `LICENSE` file for more information.
