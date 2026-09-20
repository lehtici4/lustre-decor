FROM python:3.13.7-alpine3.22 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# libpq + toolchain de build: o psycopg[binary] não tem wheel para musl/Alpine,
# e a variante pura Python depende de ctypes.util.find_library, que não
# funciona em musl (sem ldconfig). psycopg[c] compila contra a libpq instalada
# abaixo — caminho padrão recomendado para psycopg em Alpine. Imagem base
# trocada de Debian para Alpine para reduzir a superfície de vulnerabilidades
# de pacotes de SO (achado do Trivy).
RUN apk upgrade --no-cache \
    && apk add --no-cache libpq gcc musl-dev postgresql-dev \
    && addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app -h /app app

WORKDIR /app

FROM base AS development

COPY requirements ./requirements
RUN pip install --requirement requirements/development.txt

COPY --chown=app:app . .
# Vazio (dev não roda collectstatic — o Vite serve o frontend), só pra o
# WhiteNoise não reclamar de diretório inexistente ao carregar o middleware.
RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/staticfiles \
    && chown app:app /app/staticfiles

USER 10001:10001
EXPOSE 8000

CMD ["./docker/entrypoint.sh"]

FROM base AS production

COPY requirements ./requirements
RUN pip install --requirement requirements/base.txt

COPY --chown=app:app . .
RUN chmod +x /app/docker/entrypoint-production.sh \
    && mkdir -p /app/staticfiles \
    && chown app:app /app/staticfiles

USER 10001:10001
EXPOSE 8000

CMD ["./docker/entrypoint-production.sh"]
