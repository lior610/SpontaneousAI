#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Cluster attractions for all locations in the database.

.DESCRIPTION
    Runs cluster_attractions.py for every location that has embeddings.
    Use LOCATION_SLUG to cluster only one location.

.EXAMPLE
    .\cluster_all_locations.ps1
    $env:LOCATION_SLUG="london"; .\cluster_all_locations.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

python (Join-Path $ProjectRoot "data-pipeline\scripts\cluster_attractions.py")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "`nClustering complete." -ForegroundColor Green
