[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not installed or not on PATH. Install Docker Desktop with the WSL 2 backend, start it, then rerun this script. The existing localhost:5173 preview is unchanged.'
}
& docker info --format '{{.ServerVersion}}' *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker is installed but its engine is unavailable. Start Docker Desktop and wait for the engine, then rerun.'
}
& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Compose v2 is required. Enable or update the Compose plugin in Docker Desktop.'
}

$environmentPath = Join-Path $workspacePath '.env'
if (-not (Test-Path -LiteralPath $environmentPath)) {
    $randomBytes = New-Object byte[] 32
    $randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $randomGenerator.GetBytes($randomBytes) } finally { $randomGenerator.Dispose() }
    $databasePassword = ([BitConverter]::ToString($randomBytes)).Replace('-', '').ToLowerInvariant()
    $environmentText = "POSTGRES_USER=comp_review`nPOSTGRES_PASSWORD=$databasePassword`nPOSTGRES_DB=comp_review`nCORS_ORIGINS=http://localhost:8080`nDEMO_MODE=true`n"
    # CreateNew is atomic: another setup process cannot cause an overwrite.
    $fileStream = [IO.File]::Open($environmentPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    try {
        $environmentBytes = [Text.Encoding]::UTF8.GetBytes($environmentText)
        $fileStream.Write($environmentBytes, 0, $environmentBytes.Length)
    } finally { $fileStream.Dispose() }
    $databasePassword = $null
    $environmentText = $null
    Write-Host 'Created local .env with a generated database password. Existing files are never overwritten.'
}

Push-Location $workspacePath
try {
    # Quiet validation avoids printing interpolated database credentials.
    & docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose configuration is invalid. Set a non-empty POSTGRES_PASSWORD in .env.' }
    & docker compose up --build -d
    if ($LASTEXITCODE -ne 0) { throw 'Three-tier startup failed. Inspect docker compose ps and service logs.' }
    & (Join-Path $PSScriptRoot 'check-three-tier.ps1') -WaitSeconds 180
    if ($LASTEXITCODE -ne 0) { throw 'Three-tier checks failed.' }
} finally { Pop-Location }
