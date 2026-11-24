# Set up frontend, backend, and alpha from the repository root.

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

foreach ($project in @('frontend', 'backend', 'alpha')) {
    $projectRoot = Join-Path $repoRoot $project
    $example = Join-Path $projectRoot '.env.example'
    $localEnv = Join-Path $projectRoot '.env'
    if (-not (Test-Path $localEnv) -and (Test-Path $example)) {
        Copy-Item $example $localEnv
        Write-Host ('Created ' + $project + '/.env from the example; review local settings.')
    }
}

Write-Host 'Installing frontend dependencies...'
$previousHusky = $env:HUSKY
$env:HUSKY = '0'
npm ci --prefix frontend
$frontendInstallStatus = $LASTEXITCODE
if ($null -eq $previousHusky) {
    Remove-Item Env:HUSKY
} else {
    $env:HUSKY = $previousHusky
}
if ($frontendInstallStatus -ne 0) { throw 'Frontend dependency installation failed.' }

npm exec --prefix frontend -- husky install
if ($LASTEXITCODE -ne 0) { throw 'Husky setup failed.' }

Write-Host 'Installing backend dependencies...'
uv sync --project backend
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }

Write-Host 'Installing alpha dependencies...'
uv sync --project alpha
if ($LASTEXITCODE -ne 0) { throw 'Alpha dependency installation failed.' }

Write-Host 'Setup complete.'
Write-Host 'Frontend: cd frontend; npm run dev'
Write-Host 'Backend:  cd backend; uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000'
Write-Host 'Alpha UI: cd alpha; uv run streamlit run app/streamlit_app.py --server.address 127.0.0.1'
Write-Host 'Alpha test: cd alpha; uv run test_local.py'
Write-Host 'Existing .env files are preserved. Review each .env.example.'
