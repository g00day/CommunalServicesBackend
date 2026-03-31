param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Env file not found: $Path"
    }

    $line = Get-Content -LiteralPath $Path | Where-Object {
        $_ -match "^\s*$Key="
    } | Select-Object -First 1

    if (-not $line) {
        throw "Key '$Key' not found in $Path"
    }

    return ($line -split "=", 2)[1].Trim()
}

function Invoke-DockerCommand {
    param(
        [scriptblock]$Command,
        [string]$ErrorMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

if (-not (Test-Path -LiteralPath $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

$postgresDb = Get-EnvValue -Path $EnvFile -Key "POSTGRES_DB"
$postgresUser = Get-EnvValue -Path $EnvFile -Key "POSTGRES_USER"
$postgresPassword = Get-EnvValue -Path $EnvFile -Key "POSTGRES_PASSWORD"

$resolvedBackup = (Resolve-Path -LiteralPath $BackupFile).Path
$quotedPassword = $postgresPassword.Replace("'", "''")

Invoke-DockerCommand -Command { docker cp $resolvedBackup "zhkh_db:/tmp/restore.dump" } -ErrorMessage "Failed to copy backup file into container."

$restoreCommand = "export PGPASSWORD='$quotedPassword'; pg_restore -U $postgresUser -d $postgresDb --clean --if-exists --no-owner --no-privileges /tmp/restore.dump"
Invoke-DockerCommand -Command { docker compose exec -T db sh -c $restoreCommand } -ErrorMessage "Failed to restore PostgreSQL database from backup."
Invoke-DockerCommand -Command { docker compose exec -T db rm -f /tmp/restore.dump } -ErrorMessage "Failed to remove temporary restore file from container."

Write-Output "Restore completed from: $resolvedBackup"
