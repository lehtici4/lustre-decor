# Gera (ou renova) o certificado TLS autoassinado usado pelo perfil de
# produção local — ver README, "TLS local". Recebe o IP ou hostname real
# usado pra acessar a aplicação e o coloca só no SAN (Subject Alternative
# Name) — nunca no CN: certificado que depende do CN pro endereço é rejeitado
# por navegadores e clientes HTTP modernos (RFC 6125), e SAN é o campo que
# eles realmente validam. Por isso o CN aqui é um rótulo genérico, não um dos
# endereços.
#
# Uso:
#   ./infra/scripts/generate-tls-cert.ps1 192.168.9.34
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Address
)

$ErrorActionPreference = "Stop"

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$tlsDirectory = Join-Path $workspaceRoot "secrets/tls"
New-Item -ItemType Directory -Path $tlsDirectory -Force | Out-Null

# CN genérico de propósito — nunca um dos endereços (ver comentário acima).
$cn = "LustreDecor"

# Monta o SAN: números-e-pontos viram "IP:", o resto vira "DNS:". 127.0.0.1 e
# localhost sempre inclusos, pra continuar valendo pro uso local mesmo
# gerando pro IP/domínio do lab.
$sanEntries = @("IP:127.0.0.1", "DNS:localhost")
foreach ($addr in $Address) {
    if ($addr -match '^\d+\.\d+\.\d+\.\d+$') {
        $entry = "IP:$addr"
    }
    else {
        $entry = "DNS:$addr"
    }
    if ($sanEntries -notcontains $entry) {
        $sanEntries += $entry
    }
}
$san = $sanEntries -join ","

docker run --rm -v "${tlsDirectory}:/certs" alpine sh -c @"
apk add --no-cache openssl >/dev/null && openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout /certs/localhost.key -out /certs/localhost.crt \
  -subj '/CN=$cn' -addext 'subjectAltName=$san'
"@

Write-Host "Gerado: $tlsDirectory/localhost.{crt,key}"
Write-Host "SAN: $san"
