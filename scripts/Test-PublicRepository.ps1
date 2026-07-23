[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$tracked = @(& git -C $repoRoot -c core.quotepath=false ls-files)
if ($LASTEXITCODE -ne 0) {
    throw 'Git-Dateiliste konnte nicht gelesen werden.'
}

$textExtensions = @('.json', '.md', '.py', '.sql', '.txt', '.ps1', '.yml', '.yaml')
$findings = [System.Collections.Generic.List[object]]::new()
$jsonCount = 0

$patterns = [ordered]@{
    'private IPv4 address' = '(?<!\d)(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3})(?!\d)'
    'productive Matrix room ID' = '![A-Za-z0-9]{8,}:[A-Za-z0-9.-]+\.(?:org|com|net|de|io)'
    'private key' = 'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY'
    'literal bearer token' = 'Bearer\s+[A-Za-z0-9._-]{20,}'
    'literal n8n API key assignment' = 'N8N_API_KEY\s*=\s*[''"][^''"]+'
}

foreach ($relativePath in $tracked) {
    $absolutePath = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
        continue
    }

    $extension = [IO.Path]::GetExtension($absolutePath).ToLowerInvariant()
    if ($extension -notin $textExtensions) {
        continue
    }

    $content = [IO.File]::ReadAllText($absolutePath)

    if ($extension -eq '.json') {
        $jsonCount++
        try {
            $null = $content | ConvertFrom-Json
        }
        catch {
            $findings.Add([pscustomobject]@{
                File = $relativePath
                Finding = "invalid JSON: $($_.Exception.Message)"
            })
        }
    }

    foreach ($entry in $patterns.GetEnumerator()) {
        if ($content -match $entry.Value) {
            $findings.Add([pscustomobject]@{
                File = $relativePath
                Finding = $entry.Key
            })
        }
    }
}

if ($findings.Count -gt 0) {
    $findings | Sort-Object File, Finding | Format-Table -AutoSize
    throw "$($findings.Count) Veröffentlichungsschutz-Prüfung(en) fehlgeschlagen."
}

Write-Output "Öffentlichkeitsprüfung erfolgreich: $jsonCount JSON-Dateien, $($tracked.Count) versionierte Dateien."
