#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'

Set-Location -Path $PSScriptRoot

docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose logs -f
