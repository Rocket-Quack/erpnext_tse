# DSFinV-K Export

## Ziel
Der DSFinV-K Export erzeugt die gesetzliche Exportdatei fuer einen Zeitraum.
Der Export wird manuell gestartet und kann als ZIP oder TAR heruntergeladen werden.

## Voraussetzungen
- DSFinV-K Cash Point Closings vorhanden und COMPLETED
- DSFinV-K Export Filter (Business Date oder Creation Date) gesetzt
- TSE Settings: Fiskaly Zugangsdaten gueltig

## Ablauf im UI
1) Erstelle einen **DSFinV-K Export**.
2) Waehle **Format** (zip/tar).
3) Waehle **Filter Type** und Zeitraum.
4) Klicke auf **Trigger Export**.
5) Bei Status COMPLETED: **Download Export**.

## Was der Prozess macht
- Legt einen Export Job bei Fiskaly an.
- Speichert Request/Response und Provider Events.
- Aktualisiert den Status automatisch (Job + Scheduler).
- Download speichert die Datei als ERPNext File (privat).

## Wichtige Hinweise
- Export wird nur manuell gestartet.
- Download ist nur bei COMPLETED moeglich.
- Retention: Geloeschte Dateien richten sich nach `Export Retention (Days)`.
- Provider-Export selbst ist bis `time_expiration` gueltig.
