# n8n-API: Beobachtete Payload-Verfaelschung/Blockierung durch vorgeschaltete Infrastruktur

**Status:** bestaetigt reproduziert, 2026-09-14. Root Cause (welche Komponente genau) nicht identifiziert -
kein Shell-/Log-Zugriff auf den Host `172.16.1.6`, daher nur schwarzkastenartig ueber die n8n-REST-API
getestet.

## Wichtige Abgrenzung

Das hier beschriebene Verhalten ist **nicht n8n selbst zuzuschreiben**. n8n's eigene Fehlerantworten sind
JSON-formatiert (z.B. `{"message":"unauthorized"}` oder `{"message":"Workflow cannot be activated..."}`).
Die hier dokumentierten Fehlschlaege liefern stattdessen eine generische HTML-Fehlerseite
(`<pre>Internal Server Error</pre>`, HTTP 500) - das ist das Muster einer vorgeschalteten Komponente
(Reverse-Proxy/WAF/Sicherheits-Middleware), nicht von n8n's Express-Anwendung. Vermutlich, aber nicht
bewiesen: eine Content-Inspection-Schicht vor dem n8n-Container auf dieser VM.

## Kontext, in dem es auftrat

`POST`/`PUT`-Requests an die n8n Public-API (`/api/v1/workflows`, Create und Update) auf Host
`172.16.1.6:5678`, mit einem JSON-Body, der ein `n8n-nodes-base.code`-Node-Parameter (`jsCode`) mit
bestimmten JavaScript-Regex-/Escape-Mustern enthielt.

## Fund 1: Regex-Muster `\s` unmittelbar vor `$`-Anker wird blockiert

Reproduziert durch systematisches Bisektieren eines 6-Node-Workflow-Payloads (WF97-Neubau), bis auf
Minimalbeispiele reduziert. Alle folgenden Payloads waren strukturell identisch (ein `code`-Node mit
`jsCode` als einzigem Parameter), nur der Regex-Inhalt unterschied sich:

| jsCode-Fragment | HTTP-Status |
|---|---|
| `'a;'.replace(/;\s*$/, '')` | **500** |
| `'a  '.replace(/\s*$/, '')` | **500** |
| `'a '.replace(/\s$/, '')` | **500** |
| `'a;'.replace(/;$/, '')` (kein `\s`) | 200 |
| `/^select\b/i.test(raw)` (Wortgrenze, kein `\s`) | 200 |
| `'a'.replace(/a*$/, '')` (Stern+Anker, aber kein `\s`) | 200 |

**Schlussfolgerung**: der Ausloeser ist spezifisch die Zeichenfolge `\s` unmittelbar gefolgt von einem
`$`-Anker in einer Regex, unabhaengig vom Quantifikator (`*` oder keiner) und unabhaengig vom umgebenden
Code. Vermutlich eine naive ReDoS- oder generische "gefaehrliche Regex"-Heuristik, die diese Bytefolge im
Request-Body matcht.

**Betroffene HTTP-Methoden (tatsaechlich bewiesen):** `POST` (Workflow-Create) und `PUT`
(Workflow-Update) auf `/api/v1/workflows[/:id]`. **Nicht getestet:** ob dasselbe Muster in einem
Webhook-Aufruf-Body (z.B. `POST /webhook/...` mit einer Anfrage, die selbst `\s*$`-artigen Text enthaelt)
ebenfalls blockiert wird - die tatsaechlichen Diagnose-Queries in diesem Fall enthielten dieses Muster
nicht. **`GET`-Requests wurden in diesem Fall nur ohne Body getestet** (reine Workflow-/Execution-Reads)
und liefen dabei immer durch - das ist aber kein systematischer Beweis, dass `GET` grundsaetzlich sicher
ist, nur dass unsere tatsaechlichen GET-Aufrufe (keiner davon mit Body/Query-String, der das Muster
enthielt) nie blockiert wurden.

## Fund 2: Backslash-Escaping kann bei der Uebertragung veraendert werden

Bei einem `POST /api/v1/workflows` (Create), dessen `jsCode` u.a. `\\b` (JSON-escaped: ein woertlicher
Backslash gefolgt von `b`, gedacht als JS-Regex-Wortgrenze `\b`) sowie `\\t`/`\\n` (gedacht als woertliche
JS-String-Escapes `\t`/`\n`) enthielt, meldete die API **HTTP 200** (augenscheinlich erfolgreich). Ein
sofortiges Fresh-GET des gespeicherten Workflows sowie ein tatsaechlicher Testlauf des Node zeigten aber:
die Sequenzen waren zu einzelnen Steuerzeichen reduziert (aus `\\b`/`\\t`/`\\n` wurde je ein einzelnes
Backspace-/Tab-/Newline-Byte, so als waere `\\` zu `\` kollabiert und dann als JSON-Escape interpretiert
worden). Der betroffene Code-Node warf beim tatsaechlichen Ausfuehren `"Invalid or unexpected token"` -
ein rohes, unescaptes Steuerzeichen innerhalb eines einfach gequoteten JS-String-Literals ist ein
echter JavaScript-Syntaxfehler.

**Das Gefaehrliche daran**: die Verfaelschung wurde **nicht** durch einen Fehlerstatus sichtbar - der
Create-Call meldete 200/Erfolg. Sie fiel erst auf, weil der Node danach tatsaechlich testweise ausgefuehrt
wurde. Ein Deploy, der nur auf den HTTP-Status vertraut, haette einen kaputten Workflow fuer produktiv
funktionierend gehalten.

**Betroffene HTTP-Methoden (tatsaechlich bewiesen):** `POST` (Workflow-Create). Nicht separat isoliert
getestet fuer `PUT`, aber angesichts derselben vorgeschalteten Infrastruktur-Schicht als wahrscheinlich
gleichermassen betroffen einzustufen - ohne das nochmal einzeln bewiesen zu haben.

## Bewaehrter Workaround (aus den tatsaechlichen Tests, keine WAF-Umgehung)

Dies beschreibt **robuste, zulaessige Deployment-Praxis**, nicht das Aushebeln der Schutzschicht:

1. **Regex mit `\s` unmittelbar vor `$` im JS-Code eines Workflow-Payloads vermeiden.** Wo moeglich
   Klartext-String-Methoden statt Regex verwenden (`str.slice(-1)`, `str.indexOf(...)`,
   `str.toLowerCase().startsWith(...)`) - das umgeht das Muster ohne Funktionsverlust. Im konkreten Fall
   wurde die urspruengliche SQL-Guard-Logik (`/^select\b/i`, `.replace(/;\s*$/, '')`) vollstaendig ohne
   Regex neu geschrieben (`lower.slice(0,6) === 'select'`, eine `while`-Schleife mit `.slice(-1)` fuer
   Trailing-Zeichen) und war danach unauffaellig.
2. **Nach jedem API-Deploy eines Workflows mit Escape-Sequenzen oder Regex im Code: den Live-Stand fresh
   per `GET /api/v1/workflows/:id` zurueckholen und mit dem beabsichtigten Quelltext (Zeichen fuer Zeichen,
   nicht nur "Feld vorhanden") vergleichen**, bevor der Workflow als korrekt deployed gilt. Ein
   HTTP-200/Erfolg auf den Schreib-Call ist dafuer **kein** ausreichender Beleg (siehe Fund 2). Im Zweifel
   den Code-Node zusaetzlich einmal echt ausfuehren/testen, nicht nur den JSON-Diff pruefen.
3. Wenn ein Payload durchgehend mit generischem HTML-500 (statt einer n8n-JSON-Fehlermeldung) scheitert,
   zuerst bisektieren (Nodes/Felder schrittweise entfernen), bevor man einen n8n-Bug oder eigenen
   Logikfehler vermutet - in diesem Fall lag die Ursache ausserhalb von n8n.

## Hinweis fuer zukuenftige Agenten

Bei jedem Workflow-Update ueber die n8n-API, das Regex-Muster oder Backslash-Escapes im Node-Code
enthaelt: **Payload nach dem API-Transport fresh aus n8n zurücklesen und mit dem Repo-/Absicht-Quelltext
vergleichen**, bevor der Deploy als abgeschlossen gilt. Ein erfolgreicher HTTP-Status allein reicht hier
nachweislich nicht.
