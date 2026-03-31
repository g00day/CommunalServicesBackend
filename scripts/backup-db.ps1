param(
    [string]$EnvFile = ".env",
    [string]$BackupDir = "backups",
    [int]$KeepLast = 7
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

$postgresDb = Get-EnvValue -Path $EnvFile -Key "POSTGRES_DB"
$postgresUser = Get-EnvValue -Path $EnvFile -Key "POSTGRES_USER"
$postgresPassword = Get-EnvValue -Path $EnvFile -Key "POSTGRES_PASSWORD"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupFile = Join-Path $BackupDir "backup_$timestamp.dump"

$quotedPassword = $postgresPassword.Replace("'", "''")
$dumpCommand = "export PGPASSWORD='$quotedPassword'; pg_dump -U $postgresUser -d $postgresDb -F c -f /tmp/backup.dump"

Invoke-DockerCommand -Command { docker compose exec -T db sh -c $dumpCommand } -ErrorMessage "Failed to create backup inside PostgreSQL container."
Invoke-DockerCommand -Command { docker cp "zhkh_db:/tmp/backup.dump" $backupFile } -ErrorMessage "Failed to copy backup file from container."
Invoke-DockerCommand -Command { docker compose exec -T db rm -f /tmp/backup.dump } -ErrorMessage "Failed to remove temporary backup file from container."

$oldBackups = Get-ChildItem -LiteralPath $BackupDir -Filter "*.dump" | Sort-Object LastWriteTime -Descending
if ($KeepLast -gt 0 -and $oldBackups.Count -gt $KeepLast) {
    $oldBackups | Select-Object -Skip $KeepLast | Remove-Item -Force
}

Write-Output "Backup created: $backupFile"
