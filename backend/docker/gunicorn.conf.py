"""Configuração do Gunicorn em produção: HTTPS com autenticação mútua (mTLS).

O backend só aceita conexões TLS cujo cliente apresente um certificado emitido
pela CA interna do laboratório (infra/scripts/generate-internal-pki.sh). Na
prática, o único cliente com esse certificado é o waf da DMZ — mesmo quem
alcance 192.168.9.50:8000 pela rede (pfSense mal configurado, host
comprometido na DMZ sem a chave) não conversa com o backend. Os caminhos vêm
de variáveis de ambiente apontando para Docker Secrets; o
entrypoint-production.sh recusa subir se algum faltar (fail-closed).
"""

import os
import ssl

bind = "0.0.0.0:8000"
workers = 2
accesslog = "-"
errorlog = "-"

certfile = os.environ["BACKEND_TLS_CERT_FILE"]
keyfile = os.environ["BACKEND_TLS_KEY_FILE"]
ca_certs = os.environ["BACKEND_TLS_CA_FILE"]
# Exige certificado de cliente válido (assinado por ca_certs): é o "m" do mTLS.
cert_reqs = ssl.CERT_REQUIRED


def ssl_context(conf, default_ssl_context_factory):
    context = default_ssl_context_factory()
    # TLS 1.2 no mínimo, igual à borda (ssl_protocols do waf).
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context
