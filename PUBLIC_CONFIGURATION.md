# Öffentliche Konfiguration

Dieses Repository enthält ausschließlich veröffentlichbare Workflow-Vorlagen.
Interne Hosts sowie produktive n8n-, Credential-, Webhook- und Matrix-IDs
werden nicht versioniert.

Vor einem Import müssen alle Werte mit dem Präfix `CONFIGURE_` in einer lokalen
Kopie ersetzt werden. Die `.example`-Hosts und die Platzhalter-Matrix-ID sind
ebenfalls nicht lauffähige Beispieldaten.

Produktive Werte gehören ausschließlich in:

- den n8n Credential Store;
- n8n-Variablen oder eine lokale, nicht versionierte Deployment-Konfiguration;
- die jeweilige Zielinstanz nach dem Import.

Mit folgendem Befehl lässt sich der öffentliche Stand prüfen:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-PublicRepository.ps1
```

Der Test prüft JSON-Syntax, private IPv4-Bereiche, produktive Matrix-Raum-IDs
und typische Klartext-Secret-Muster. Er kann nicht garantieren, dass niemals
sensible Daten eingecheckt werden; neue Konfigurationsarten müssen bei Bedarf
in die Prüfmuster aufgenommen werden.
