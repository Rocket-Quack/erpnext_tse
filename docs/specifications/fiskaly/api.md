# Fiskaly API Spezifikation (ERPNext TSE)

Diese Datei beschreibt die in der App verwendete Fiskaly API auf Basis der
Implementierung in `erpnext_tse/erpnext_tse/tss_providers/fiskaly.py` und den
zugehoerigen DocTypes. Sie ist keine vollstaendige offizielle API-Referenz.

## Basis-URLs und Konfiguration
- Core API Base URL (Default): `https://kassensichv-middleware.fiskaly.com/api/v2`
- DSFinV-K Base URL (Default): `https://dsfinvk.fiskaly.com/api/v1`
- Konfigurationsfelder in "TSE Settings":
  - `api_key`, `api_secret` (Pflicht fuer Auth)
  - `base_url`, `dsfinvk_base_url` (optional ueberschreiben)
  - `access_token`, `refresh_token` + `*_expires_at` (nur intern, read-only)
  - `organization_id`, `token_environment`, `last_auth_*` (nur intern)
  - `recovery_sync_enabled` (Recovery UI)
  - `enable_debug_logging` (nur fuer Debug)

## Authentifizierung (Core API)
Endpoint: `POST /auth`

Payload:
```json
{
  "api_key": "<api_key>",
  "api_secret": "<api_secret>"
}
```

Verhalten:
- Access/Refresh Token werden in den TSE Settings gespeichert.
- Token-Claims liefern `organization_id` und `env` (token_environment).
- Bei 401 oder anderen 4xx/5xx wird der Fehler gecleart und `last_auth_*` gesetzt.
- `ensure_valid_access_token()` re-authentifiziert automatisch, wenn das Token
  fehlt oder abgelaufen ist (Skew: 60s).

## HTTP-Standardverhalten
- Header:
  - `Authorization: Bearer <access_token>`
  - `Content-Type: application/json`
- Timeouts:
  - Core API: 15s
  - DSFinV-K API: 30s
- 401 wird einmalig mit neuem Token wiederholt.
- JSON-Responses ohne `status_code` werden mit `status_code` angereichert.
- Non-JSON Responses werden als Fehler behandelt.

## Fachlicher Gesamtprozess (End-to-End)
1) TSE Settings konfigurieren, `Test Auth` ausfuehren.
2) TSE Security Device anlegen (TSS), Admin PUK sichern.
3) TSS deployen (UNINITIALIZED) und initialisieren (INITIALIZED).
4) TSE Client anlegen und beim Provider registrieren.
5) POS Profile fachlich erstellen und im TSE Client verknuepfen.
6) POS Invoice erzeugt beim Submit eine TSE Transaction (Start -> Finish).
7) Signatur, QR-Daten und Status werden in der TSE Transaction gespeichert.

## ERPNext DocTypes und Verantwortlichkeiten
- `TSE Settings`: globale Zugangsdaten, Token-Status, Provider-URLs, Recovery-Flag.
- `TSE Security Device`: TSS-Stammdaten, Status, Admin PUK/PIN, Zertifikat, Events.
- `TSE Client`: Client-ID, Seriennummer, POS Profile, Status, Events.
- `TSE Transaction`: Transaktionsstatus, Revision, Signatur, QR-Daten, Schema-Log.

## Lebenszyklus und Statuswechsel
TSS (Security Device):
- `DRAFT` -> `CREATED` (Create) -> `UNINITIALIZED` (Deploy)
- `UNINITIALIZED` -> `INITIALIZED` (Initialize)
- `INITIALIZED`/`UNINITIALIZED` -> `DISABLED` (Disable, irreversibel)
- Recovery kann `ORPHANED` setzen, Fehler -> `ERROR`

Client:
- `DRAFT` -> `REGISTERED` (Create bei Provider)
- `REGISTERED` -> `DEREGISTERED` (Deregister)
- `DEREGISTERED` -> `REGISTERED` (Register)
- Recovery kann `ORPHANED` setzen, Fehler -> `ERROR`

## Validierungen und fachliche Regeln
- TSE Integration muss aktiviert sein (`TSE Settings.enabled`).
- TSE Transaction nur mit `INITIALIZED` TSS und `REGISTERED` Client.
- Pro POS Profile ist genau ein TSE Client erlaubt (Unique-Constraint).
- TSE Transactions koennen nicht geloescht oder storniert werden (hard block).
- Fehlende Mappings fuer VAT/Payment Types brechen den Prozess ab.

## POS-Integration und Transaktionsfluss
- Hook `before_submit` erstellt und beendet die TSE Transaction.
- Falls bereits eine verknuepfte Transaction `FINISHED` ist, erfolgt kein neuer Start.
- Falls bereits eine Transaction existiert, aber nicht `FINISHED` ist, wird blockiert.
- `tx_revision` startet bei 1 und wird beim Finish erhoeht.

## IDs und UUIDs
- `tss_id`, `client_id`, `serial_number`, `tx_id`, `export_id`, `closing_id`
  werden als UUIDv4 erzeugt.

## Logging und Audit
- Provider-Events werden in Child-Tabellen gespeichert:
  - `TSE Security Device Provider Event`
  - `TSE Client Provider Event`
- Pro Event: Zeit, Aktion, Status vorher/nachher, HTTP-Status, Error-Code, Payload.

## TSS (Security Device) Endpunkte
Create (TSS anlegen):
- `PUT /tss/{tss_id}` (payload ist leer)
- `tss_id` wird als UUIDv4 erzeugt

Deploy / Initialize / Disable:
- `PATCH /tss/{tss_id}` mit `{"state": "UNINITIALIZED"}`
- `PATCH /tss/{tss_id}` mit `{"state": "INITIALIZED"}`
- `PATCH /tss/{tss_id}` mit `{"state": "DISABLED"}`

Read:
- `GET /tss` (Liste)
- `GET /tss/{tss_id}`

Verwendete Response-Felder:
- `id` / `_id`, `state`
- `admin_puk`, `certificate`
- `serial_number`, `time_init`, `time_disable`

Lokale Status (DocType `TSE Security Device`):
- `DRAFT`, `CREATED`, `UNINITIALIZED`, `INITIALIZED`, `DISABLED`, `ORPHANED`, `ERROR`
- Provider-Mapping im Recovery: `DELETED` -> `DISABLED`

## Admin-Operationen (TSS)
Admin-Auth:
- `POST /tss/{tss_id}/admin/auth`
```json
{ "admin_pin": "<admin_pin>" }
```

Admin-PIN setzen/wechseln:
- `PATCH /tss/{tss_id}/admin`
```json
{ "admin_puk": "<admin_puk>", "new_admin_pin": "<new_pin>" }
```

Logout:
- `POST /tss/{tss_id}/admin/logout`

Hinweise aus der App-Logik:
- Falls kein `admin_pin` gespeichert ist, wird ein 8-stelliger PIN erzeugt
  und per `change_admin_pin` gesetzt.
- Viele Operationen (z. B. Client-Create, Initialize/Disable) verlangen
  vorherige Admin-Authentifizierung.

## Client Endpunkte
Create (Client anlegen):
- `PUT /tss/{tss_id}/client/{client_id}`
- `client_id` und `serial_number` werden als UUIDv4 erzeugt
```json
{
  "serial_number": "<uuid>",
  "metadata": {
    "company": "<Company>",
    "pos_profile": "<POS Profile>",
    "tse_client_name": "<Client Name>",
    "tse_client_docname": "<Docname>"
  }
}
```

Register / Deregister:
- `PATCH /tss/{tss_id}/client/{client_id}` mit `{"state": "REGISTERED"}`
- `PATCH /tss/{tss_id}/client/{client_id}` mit `{"state": "DEREGISTERED"}`

Read:
- `GET /tss/{tss_id}/client`
- `GET /tss/{tss_id}/client/{client_id}`

Lokale Status (DocType `TSE Client`):
- `DRAFT`, `REGISTERED`, `DEREGISTERED`, `ORPHANED`, `ERROR`

Recovery-Matching (Metadata Keys):
- `tse_client_docname`, `tse_client_name`
- `client_name`, `name`
- `pos_profile`, `pos_profile_name`
- `company`

## Transaktionen (SIGN DE - upsertTransaction)
List / Get:
- `GET /tss/{tss_id}/tx`
- `GET /tss/{tss_id}/tx/{tx_id}`
  - Optional Query: `limit`, `offset`, `order_by`, `order` (Recovery nutzt `time_start` + `asc`).

Upsert:
- `PUT /tss/{tss_id}/tx/{tx_id}?tx_revision=<n>`

Start:
- `state: "ACTIVE"`, `client_id` gesetzt, `tx_revision = 1`
```json
{
  "state": "ACTIVE",
  "client_id": "<client_id>"
}
```

Finish:
- `state: "FINISHED"`, `tx_revision` erhoeht
- `schema` wird uebergeben (siehe unten)
```json
{
  "state": "FINISHED",
  "client_id": "<client_id>",
  "schema": { "...": "..." }
}
```

Cancel (optional):
- `state: "CANCELLED"` mit optionalem `schema`

Schema-Format (aus POS Invoice gebaut):
```json
{
  "standard_v1": {
    "receipt": {
      "receipt_type": "RECEIPT",
      "amounts_per_vat_rate": [
        { "vat_rate": "NORMAL", "amount": "19.00" }
      ],
      "amounts_per_payment_type": [
        { "payment_type": "CASH", "amount": "10.00" }
      ]
    }
  }
}
```

Schema-Aufbau in der App:
- VAT-Rates kommen aus "TSE VAT Rate" Mapping (Steuerkonto -> VAT Code).
- Payment Types kommen aus "TSE Payment Type" (Mode of Payment -> Code).
- Wechselgeld wird von den Payment-Summen abgezogen.
- Amounts werden als Strings mit 2 Dezimalstellen geschrieben.
- Aktuell werden nur 19% und 7% Steuersaetze verarbeitet.

Verwendete Response-Felder fuer TSE Transaction:
- `_id`, `state`, `time_start`, `time_end`
- `revision`, `number`
- `qr_code_data`
- `signature.counter`

## DSFinV-K API
Exports:
- `PUT /exports/{export_id}` (export_id UUIDv4, falls nicht angegeben)
  - Payload muss `by_creation_date` **oder** `by_business_date` enthalten
  - Optional: `client_id`, `format`, `metadata`
- `GET /exports` (Query: `limit`, `offset`, `order_by`, `order`, `states`,
  `client_id`, `business_date_start`, `business_date_end`)
- `GET /exports/{export_id}`
- `DELETE /exports/{export_id}`
- `GET /exports/{export_id}/href`
- `GET /exports/{export_id}/metadata`
- `PUT /exports/{export_id}/metadata`
- `GET /exports/{export_id}/download` (liefert ZIP Bytes)

Cash Registers:
- `GET /cash_registers`
- `GET /cash_registers/{cash_register_id}`
- `PUT /cash_registers/{cash_register_id}`
- `GET /cash_registers/{cash_register_id}/metadata`
- `PUT /cash_registers/{cash_register_id}/metadata`

Cash Point Closings:
- `GET /cash_point_closings`
- `GET /cash_point_closings/{closing_id}`
- `GET /cash_point_closings/{closing_id}/details`
- `GET /cash_point_closings/{closing_id}/reports`
- `GET /cash_point_closings/{closing_id}/metadata`
- `PUT /cash_point_closings/{closing_id}/metadata`
- `PUT /cash_point_closings/{closing_id}`
- `DELETE /cash_point_closings/{closing_id}`

## Recovery-Sync (Integration)
- Security Devices: nutzt `GET /tss` und gleicht lokale TSS an.
- Clients: nutzt `GET /tss/{tss_id}/client` fuer jede TSS.
- Transactions: nutzt `GET /tss/{tss_id}/tx` je TSS, aktualisiert lokale Felder
  und markiert fehlende Eintraege als `ORPHANED`.
- Fehlende Provider-Eintraege werden lokal als `ORPHANED` markiert.
- Fehlende Admin PUKs werden nach Recovery per Dialog nachgepflegt.
- Falls der Provider einen `admin_puk` liefert und lokal keiner existiert, wird er gesetzt.
