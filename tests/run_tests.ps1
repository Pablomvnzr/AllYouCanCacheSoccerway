$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose build cache-service metrics-service scraper-service traffic-generator
if ($LASTEXITCODE -ne 0) { throw 'Falló la construcción' }
$services = @{'test_cache.py'='cache-service'; 'test_metrics.py'='metrics-service'; 'test_parsers.py'='scraper-service'; 'test_distributions.py'='traffic-generator'; 'test_traffic.py'='traffic-generator'; 'test_preload.py'='scraper-service'}
foreach ($test in $services.Keys) {
    docker compose run --rm --no-deps --volume "${PWD}:/repo" --entrypoint python $services[$test] -m unittest discover -s /repo/tests -p $test -v
    if ($LASTEXITCODE -ne 0) { throw "Falló $test" }
}
