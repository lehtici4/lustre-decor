"""Falha de autenticação vira evento `login_failed` no log estruturado,
venha de onde vier (VULN-06).

O receptor fica no sinal `user_login_failed`, que o próprio `authenticate()`
do Django dispara — vale para o login da API (/api/v1/auth/login/), para o
login do Django Admin / django-two-factor (/account/login/) e para qualquer
caminho futuro que autentique por senha. Antes o evento era emitido à mão só
no serviço da API, e o login do admin passava sem registro.

O nome de usuário tentado NÃO vai para o log (pode ser um e-mail; ver
pseudonimização no documento de arquitetura, §7.3). A correlação de força
bruta é por origem (`origin`, IP real do cliente — apps/core/net.py), que é o
que as regras 100101/100102 do Wazuh e a jail lustre-auth usam.
"""

import logging

from apps.core.net import client_ip

logger = logging.getLogger("apps.accounts")


def log_login_failed(sender, credentials=None, request=None, **kwargs):
    logger.warning(
        "login_failed",
        extra={
            "origin": client_ip(request) if request is not None else None,
            "path": getattr(request, "path", None),
            "reason": "bad_credentials",
        },
    )
