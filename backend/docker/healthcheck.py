"""Healthcheck do container de produção: GET https://localhost:8000/api/v1/health/.

Como o Gunicorn exige certificado de cliente (mTLS), o healthcheck se
apresenta com o certificado do próprio backend (emitido com clientAuth além de
serverAuth) e valida o servidor contra a CA interna, pelo nome "localhost"
(presente no SAN).
"""

import os
import ssl
import sys
import urllib.request

context = ssl.create_default_context(cafile=os.environ["BACKEND_TLS_CA_FILE"])
context.load_cert_chain(os.environ["BACKEND_TLS_CERT_FILE"], os.environ["BACKEND_TLS_KEY_FILE"])

try:
    with urllib.request.urlopen("https://localhost:8000/api/v1/health/", timeout=2, context=context) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception as exc:  # noqa: BLE001 - qualquer falha = unhealthy
    print(f"healthcheck: {exc}", file=sys.stderr)
    sys.exit(1)
