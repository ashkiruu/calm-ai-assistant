[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8010,
    [string]$PythonPath
)

# Start CALM on every local network interface for a Quest on the same Wi-Fi.
# This is intentionally a foreground command: the facilitator can see startup
# errors and any Windows Firewall prompt instead of leaving a hidden server
# running after a lesson.
$assistantRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $venvPython = Join-Path $assistantRoot 'venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        $PythonPath = $venvPython
    }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) {
            throw 'Python was not found. Pass -PythonPath with the assistant environment Python executable.'
        }
        $PythonPath = $pythonCommand.Source
    }
}

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python executable not found: $PythonPath"
}

Write-Host "Starting CALM for the local network on port $Port..."
Write-Host 'Use the PC IPv4 address (not 127.0.0.1) in the Quest calm-assistant.json file.'
Push-Location -LiteralPath $assistantRoot
try {
    & $PythonPath -m uvicorn server:app --host 0.0.0.0 --port $Port
}
finally {
    Pop-Location
}
