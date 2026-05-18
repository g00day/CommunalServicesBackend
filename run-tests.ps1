param(
    [switch]$NoBuild,
    [switch]$KeepContainers
)

$ErrorActionPreference = "Stop"

$composeArgs = @(
    "-f", "docker-compose.test.yml",
    "up"
)

if (-not $NoBuild) {
    $composeArgs += "--build"
}

$composeArgs += @(
    "--abort-on-container-exit",
    "--exit-code-from", "backend-tests",
    "--remove-orphans"
)

try {
    & docker compose @composeArgs
    $exitCode = $LASTEXITCODE
}
finally {
    if (-not $KeepContainers) {
        & docker compose -f docker-compose.test.yml down --remove-orphans | Out-Null
    }
}

exit $exitCode
