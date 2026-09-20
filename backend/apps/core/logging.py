import logging

# Nem todo warning merece tirar alguém do sono: só os eventos abaixo (força
# bruta bloqueada, tentativa de acessar objeto de outro usuário) são
# acionáveis o suficiente para gerar um alerta por e-mail, em vez de só
# aparecer no log estruturado — ver LOGGING em config/settings/base.py.
ALERT_EVENTS = {"request_throttled", "forbidden_object_access"}

# "message" e "asctime" não existem num LogRecord recém-criado — só aparecem
# depois que ALGUM formatter roda (Formatter.format() seta os dois como
# efeito colateral). Como o mesmo record é compartilhado entre handlers
# (console roda antes deste), sem essa exclusão explícita eles vazariam
# como se fossem campos de "extra" de verdade.
_STANDARD_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class SecurityAlertFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage() in ALERT_EVENTS


class SecurityAlertFormatter(logging.Formatter):
    """Corpo do e-mail de alerta: a mensagem do evento mais os campos extras
    que ele carregar (user_id, origin, path, model, object_id...). Os dois
    eventos alertáveis não carregam os mesmos campos, por isso monta a lista
    dinamicamente em vez de um formato fixo com %(campo)s — evitaria erro de
    formatação quando um campo não existisse no record."""

    def format(self, record: logging.LogRecord) -> str:
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_ATTRS
        }
        details = ", ".join(f"{key}={value}" for key, value in sorted(extras.items()))
        base = f"[{self.formatTime(record)}] {record.getMessage()}"
        return f"{base} ({details})" if details else base
