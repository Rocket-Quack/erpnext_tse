<div align="center">
  <p>
    <img src="/docs/assets/TSE_APP_LOGO.png" alt="ERPNext TSE Logo" width="164"/>
  </p>
    <h1>TSE ERPNext Installation</h1>
</div>

Diese Anleitung beschreibt die Installation der TSE-App für ERPNext auf einer bestehenden Bench-Umgebung.  

## Voraussetzungen

Bevor du beginnst, stelle sicher, dass:

- Eine funktionierende **Frappe Bench** Umgebung vorhanden ist.
- **ERPNext** ist installiert und Funktionsbereit
- Du dich im Verzeichnis deiner Bench befindest, z. B.:


## 1. App installieren

Pfade und Namen in dieser Anleitung müssen an die jeweillige Umgebung angepasst werden.

1. Wechsle in dein Bench-Verzeichnis:

```bash
cd /pfad/zu/deiner/frappe-bench
```

2. Holen der TSE App.

```bash
bench get-app https://github.com/Rocket-Quack/erpnext_tse.git --branch version-15
```

4. Auflistung der Sites:

```bash
ls sites
```

Beispiel: `site1.local`, `mein-kunde.de` usw.

5. Installiere die App auf der gewünschten Site, z. B.:

```bash
bench --site site1.local install-app erpnext_tse
```

6. Im Anschluss Migration ausführen

```bash
bench --site site1.local migrate
```

## 2. Rollen & Berechtigungen

#TODO

