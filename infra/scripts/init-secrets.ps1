$ErrorActionPreference = "Stop"

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$secretsDirectory = Join-Path $workspaceRoot "secrets"
$requiredSecrets = @(
    @{ Name = "django_secret_key.txt"; Bytes = 48 },
    @{ Name = "postgres_password.txt"; Bytes = 32 },
    @{ Name = "postgres_runtime_password.txt"; Bytes = 32 }
)

New-Item -ItemType Directory -Path $secretsDirectory -Force | Out-Null

foreach ($secret in $requiredSecrets) {
    $target = Join-Path $secretsDirectory $secret.Name
    if (Test-Path -LiteralPath $target) {
        Write-Host "Preservado: $target"
        continue
    }

    $randomBytes = [byte[]]::new($secret.Bytes)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($randomBytes)
    }
    finally {
        $generator.Dispose()
    }
    $value = [Convert]::ToBase64String($randomBytes)
    [System.IO.File]::WriteAllText($target, $value, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Criado: $target"
}
