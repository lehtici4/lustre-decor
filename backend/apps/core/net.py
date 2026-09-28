"""IP de origem do cliente atrás do waf.

O Nginx do waf repassa `X-Forwarded-For: <o que o cliente mandou>, <IP real>`
($proxy_add_x_forwarded_for): tudo antes do último item é controlado pelo
cliente e não vale nada. Com exatamente um proxy confiável na frente
(REST_FRAMEWORK["NUM_PROXIES"] = 1 — e o backend só aceita conexões do waf,
via mTLS), o IP real é o ÚLTIMO item. Mesma regra que o throttling do DRF
passa a usar (SimpleRateThrottle.get_ident), para que log e limite de taxa
falem do mesmo endereço.
"""

from rest_framework.settings import api_settings


def client_ip(request) -> str | None:
    meta = getattr(request, "META", {})
    remote_addr = meta.get("REMOTE_ADDR")
    xff = meta.get("HTTP_X_FORWARDED_FOR")
    num_proxies = api_settings.NUM_PROXIES
    if not xff or not num_proxies:
        return remote_addr
    addrs = [addr.strip() for addr in xff.split(",") if addr.strip()]
    if not addrs:
        return remote_addr
    return addrs[-min(num_proxies, len(addrs))]
