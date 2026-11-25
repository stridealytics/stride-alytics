<#
.SYNOPSIS
    Apply pending database migrations in order.

.DESCRIPTION
    Connects to the database in $env:DATABASE_URL (or the local
    docker-compose default) and runs every migrations/*.sql file in
    lexical order, except *_down.sql. Applied files are recorded in
    public.schema_migrations and skipped next time.

    -Baseline records every file as applied WITHOUT running it. Use it once
    on a database that already has them (for example one migrated through the
    Supabase MCP or SQL editor).

.EXAMPLE
    .\database\scripts\apply_migrations.ps1
    .\database\scripts\apply_migrations.ps1 -Baseline
#>

[CmdletBinding()]
param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [switch]$Baseline
)

$ErrorActionPreference = "Stop"
$ROOT = (Resolve-Path "$PSScriptRoot\..\..\").Path
$migDir = Join-Path $ROOT "database\migrations"

if (-not $DatabaseUrl) {
    $DatabaseUrl = "postgresql://postgres:postgres@localhost:5432/stridealytics"
}

function Invoke-Psql {
    param([string[]]$PsqlArgs)
    $out = & psql $DatabaseUrl -v ON_ERROR_STOP=1 @PsqlArgs
    if ($LASTEXITCODE -ne 0) { throw "psql failed: $($PsqlArgs -join ' ')" }
    return $out
}

Write-Host "Applying migrations from $migDir" -ForegroundColor Cyan
Write-Host ""

Invoke-Psql @("-q", "-c", @"
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;
"@) | Out-Null

$files = Get-ChildItem -Path $migDir -Filter "*.sql" |
    Where-Object { $_.Name -notlike "*_down.sql" } |
    Sort-Object Name

foreach ($f in $files) {
    $seen = Invoke-Psql @("-tA", "-c", "SELECT 1 FROM public.schema_migrations WHERE filename = '$($f.Name)'")
    if ((($seen | Out-String).Trim()) -eq "1") {
        Write-Host "  == $($f.Name) (already applied)" -ForegroundColor DarkGray
        continue
    }
    $record = "INSERT INTO public.schema_migrations (filename) VALUES ('$($f.Name)');"
    if ($Baseline) {
        Write-Host "  .. $($f.Name) (recorded, not run)" -ForegroundColor Yellow
        Invoke-Psql @("-q", "-c", $record) | Out-Null
    } else {
        Write-Host "  -> $($f.Name)" -ForegroundColor Yellow
        # One psql session: the file and its record, so an interruption cannot apply without recording.
        $sql = (Get-Content -Raw -Path $f.FullName) + "`n" + $record + "`n"
        $sql | & psql $DatabaseUrl -v ON_ERROR_STOP=1 -q -f - | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "psql failed on $($f.Name)" }
    }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host ""
Write-Host "Verifying schema:" -ForegroundColor Cyan
& psql $DatabaseUrl -c "\dt" -c "\dv"
