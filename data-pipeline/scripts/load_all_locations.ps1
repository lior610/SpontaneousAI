#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Load places from all locations into the attractions database.

.DESCRIPTION
    Finds all places_enriched.json files under data-pipeline/scrapers/data/*/
    and runs load_places_to_db.py for each. Location slug is inferred from
    the parent folder (e.g. london, ny).

.EXAMPLE
    .\load_all_locations.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$DataDir = Join-Path $ProjectRoot "data-pipeline\scrapers\data"

$jsonFiles = Get-ChildItem -Path $DataDir -Filter "places_enriched.json" -Recurse -ErrorAction SilentlyContinue

if (-not $jsonFiles) {
    Write-Error "No places_enriched.json found under $DataDir"
    exit 1
}

foreach ($file in $jsonFiles) {
    $slug = $file.Directory.Name
    Write-Host "`n=== Loading $slug ===" -ForegroundColor Cyan
    $env:PLACES_JSON = $file.FullName
    python (Join-Path $ProjectRoot "data-pipeline\scripts\load_places_to_db.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to load $slug"
        exit $LASTEXITCODE
    }
}

Write-Host "`nDone. Loaded $($jsonFiles.Count) location(s)." -ForegroundColor Green
