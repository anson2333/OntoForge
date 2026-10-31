param([switch]$SkipIntegration, [switch]$SkipBrowser)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Root 'backend/.venv/Scripts/python.exe'
$Container = "ontoforge-acceptance-$PID"
$Started = $false
function Check-Exit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)" } }
Push-Location $Root
try {
    if (!(Test-Path $Python)) { throw 'Create backend/.venv and install backend/requirements.txt first.' }
    if (!$SkipIntegration) {
        docker info --format '{{.ServerVersion}}'; Check-Exit 'Docker availability'
        # This suite erases its database. Always create an isolated container.
        $Password = [guid]::NewGuid().ToString('N')
        docker run -d --name $Container -p '127.0.0.1::7687' -e "NEO4J_AUTH=neo4j/$Password" neo4j:5
        Check-Exit 'Start isolated Neo4j'; $Started = $true
        $Binding = docker port $Container 7687/tcp
        Check-Exit 'Find Neo4j test port'
        $env:ONTOFORGE_TEST_NEO4J_URI = "bolt://$($Binding.Trim())"
        $env:NEO4J_URI = $env:ONTOFORGE_TEST_NEO4J_URI
        $env:NEO4J_USER = 'neo4j'; $env:NEO4J_PASSWORD = $Password
        $env:ONTOFORGE_REQUIRE_INTEGRATION = 'true'
        $Ready = $false
        for ($Attempt = 0; $Attempt -lt 90; $Attempt++) {
            & $Python -c 'import os; from neo4j import GraphDatabase; d=GraphDatabase.driver(os.environ["NEO4J_URI"],auth=("neo4j",os.environ["NEO4J_PASSWORD"])); d.verify_connectivity(); d.close()' 2>$null
            if ($LASTEXITCODE -eq 0) { $Ready = $true; break }
            Start-Sleep -Seconds 1
        }
        if (!$Ready) { throw 'Isolated Neo4j did not become ready.' }
        & $Python -m pytest backend/tests -q --no-cov
    } else {
        & $Python -m pytest backend/tests -q --no-cov --ignore=backend/tests/test_integration.py --ignore=backend/tests/test_ingestion_integration.py --ignore=backend/tests/test_api_integration.py
    }
    Check-Exit 'Backend tests'
    & $Python -m backend.scripts.prepare_cv_corpus --check-only; Check-Exit 'CV temporal manifest'
    Push-Location frontend
    try {
        npm run type-check; Check-Exit 'TypeScript'
        npm run lint; Check-Exit 'ESLint'
        npm run build; Check-Exit 'Production build'
    } finally { Pop-Location }
    if (!$SkipBrowser) {
        if ($SkipIntegration) { throw 'Browser validation requires the isolated Neo4j; omit -SkipIntegration or use -SkipBrowser.' }
        & $Python -m backend.scripts.windows_demo; Check-Exit 'Browser walkthrough'
    }
    if ($SkipIntegration -or $SkipBrowser) { Write-Host 'Partial validation passed; skipped stages are not delivery acceptance.' }
    else { Write-Host 'Technical validation passed. Real LLM quality and historical gap evaluation remain separate evidence requirements.' }
} finally {
    if ($Started) { docker stop $Container | Out-Null }
    Pop-Location
}
