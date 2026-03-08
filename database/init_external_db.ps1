#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Initialize the external attractions database schema.

.DESCRIPTION
    Creates the attractions database (if missing) and runs the schema.
    Uses POSTGRES_* from .env - ensure .env is configured for the external DB.

.EXAMPLE
    .\database\init_external_db.ps1
#>
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Load .env
Get-Content "$ProjectRoot\.env" | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim().Trim('"'), 'Process')
    }
}

$Host = $env:POSTGRES_HOST
$Port = $env:POSTGRES_PORT
$User = $env:POSTGRES_USER
$Password = $env:POSTGRES_PASSWORD
$AttractionsDb = $env:POSTGRES_ATTRACTIONS_DB

if (-not $Host -or -not $Password) {
    Write-Error "POSTGRES_HOST and POSTGRES_PASSWORD must be set in .env"
    exit 1
}

$env:PGPASSWORD = $Password
$PsqlPath = 'C:\Program Files\pgAdmin 4\runtime\psql.exe'
if (-not (Test-Path $PsqlPath)) {
    $PsqlPath = (Get-Command psql -ErrorAction SilentlyContinue).Source
}
if (-not $PsqlPath) {
    Write-Error "psql not found. Install PostgreSQL or pgAdmin."
    exit 1
}

Write-Host "Creating database '$AttractionsDb' if not exists..." -ForegroundColor Cyan
& $PsqlPath -h $Host -p $Port -U $User -d postgres -c "CREATE DATABASE $AttractionsDb" 2>$null
# Ignore error if DB already exists (error 42P04)

Write-Host "Running attractions schema..." -ForegroundColor Cyan
& $PsqlPath -h $Host -p $Port -U $User -d $AttractionsDb -f "$ProjectRoot\database\init_attractions_only.sql"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Schema init failed"
    exit $LASTEXITCODE
}
Write-Host "Attractions database ready." -ForegroundColor Green

