[CmdletBinding()]
param([ValidateRange(1, 600)][int]$WaitSeconds = 20)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not installed or not on PATH. No three-tier containers can be checked; the existing local preview is separate.'
}
$baseUrl = 'http://localhost:8080'
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$ready = $false
do {
    try {
        $frontend = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/health" -TimeoutSec 3
        $backend = Invoke-RestMethod -Uri "$baseUrl/api/ready" -TimeoutSec 3
        if ($frontend.StatusCode -eq 200 -and $backend) { $ready = $true; break }
    } catch {
        if ((Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
    }
} while ((Get-Date) -lt $deadline)

if (-not $ready) {
    throw 'The frontend and database-backed API readiness checks did not pass at localhost:8080. Inspect docker compose ps and docker compose logs initialize backend frontend.'
}
$summary = Invoke-RestMethod -Uri "$baseUrl/api/v1/summary" -TimeoutSec 10
if (-not $summary.total_employees -or $summary.total_employees -lt 1) {
    throw 'The API is reachable but the seeded employee dataset is empty.'
}
$comparisons = Invoke-RestMethod -Uri "$baseUrl/api/v1/comparisons?limit=1" -TimeoutSec 10
if (-not $comparisons.items -or $comparisons.items.Count -lt 1) {
    throw 'Employees exist but analysis has not produced a reviewable comparison.'
}
Write-Host "Three-tier check passed: nginx frontend -> FastAPI -> PostgreSQL; $($summary.total_employees) employees and comparison data available."
Write-Host "Open $baseUrl"
