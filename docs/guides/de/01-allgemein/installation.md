<div align="center">
  <p>
    <img src="/docs/assets/TSE_APP_LOGO.png" alt="ERPNext TSE Logo" width="164"/>
  </p>
    <h1>TSE ERPNext Installation</h1>
</div>

Diese Anleitung beschreibt die Installation der TSE-App fuer ERPNext in einer bestehenden Bench-Umgebung.

## Voraussetzungen

Bevor du beginnst, stelle sicher, dass:

- Eine funktionierende **Frappe Bench** Umgebung vorhanden ist.
- **ERPNext** installiert und funktionsbereit ist.
- Du dich im Verzeichnis deiner Bench befindest, z. B.: `/pfad/zu/deiner/frappe-bench`.
- Du Zugriff auf die Ziel-Site und die Rolle **System Manager** oder **TSE Admin** hast.

## 1. App installieren

Pfade und Namen in dieser Anleitung muessen an die jeweilige Umgebung angepasst werden.

1. Wechsle in dein Bench-Verzeichnis:

```bash
cd /pfad/zu/deiner/frappe-bench
```

2. Hole die TSE App:

```bash
bench get-app https://github.com/Rocket-Quack/erpnext_tse.git --branch version-15
```

3. Liste die vorhandenen Sites auf:

```bash
ls sites
```

Beispiel: `site1.local`, `mein-kunde.de` usw.

4. Installiere die App auf der gewuenschten Site, z. B.:

```bash
bench --site site1.local install-app erpnext_tse
```

5. Fuehre im Anschluss die Migration aus:

```bash
bench --site site1.local migrate
```

6. Optional, falls Services nicht automatisch neu laden:

```bash
bench restart
```

## 2. Rollen & Berechtigungen

- Bei der Installation wird die Rolle **TSE Admin** automatisch angelegt.
- Zugriff auf **TSE Settings**, **TSE Security Device**, **TSE Client**, **TSE Transaction** und die **DSFinV-K** Doctypes haben **System Manager** und **TSE Admin**.
- Weise die Rolle **TSE Admin** allen Benutzern zu, die die Einrichtung und den Betrieb verantworten.

## 3. Naechste Schritte

- Starte mit der Erstkonfiguration in `docs/guides/de/01-allgemein/configuration.md`.
- Lege zuerst ein **TSE Security Device (TSS)** an, danach **TSE Clients** und verknuepfe **POS Profile**.
- Pruefe die taegliche Nutzung in `docs/guides/de/01-allgemein/usage.md`.

![TSE Uebersichtsseite in ERPNext](/docs/assets/TSE-Settings/OVERVIEW.png)
