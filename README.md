# Lustre Decor

E-commerce acadêmico de produtos para casa, estruturado para demonstrar desenvolvimento seguro, segmentação e princípios de Zero Trust. Não há integração nem simulação de pagamento — é um recorte funcional para o laboratório de segurança.

## Funcionalidades

- Catálogo público de produtos.
- Cadastro, login e logout de clientes.
- Carrinho (adicionar, alterar quantidade, remover) com autorização por objeto.
- Registro de pedidos a partir do carrinho (sem pagamento) e histórico "Meus pedidos".
- Administração via Django Admin, com MFA (TOTP) obrigatório para contas de staff/superusuário.
- Logs de segurança estruturados em JSON (login, logout, cadastro, bloqueio por força bruta, acesso negado a objeto de outro usuário, criação de pedido, alterações administrativas).
- Alertas por e-mail para os dois eventos mais acionáveis (bloqueio por força bruta e tentativa de acessar objeto de outro usuário) — ver "Alertas de segurança" abaixo.
- Regras de negócio isoladas em `backend/apps/core/services/`, separadas das views.
- Perfil de produção local com Nginx + ModSecurity/OWASP CRS (estáticos + proxy reverso + rate limiting + WAF) e backend via Gunicorn.

## Pré-requisitos

- Docker com Docker Compose v2
- PowerShell 7+ (Windows) **ou** bash (Linux/macOS, inclusive as VMs Ubuntu do laboratório) para os scripts locais de inicialização — ver `infra/scripts/`, há uma versão de cada um dos dois lados.

## Inicialização

```powershell
Copy-Item .env.example .env
./infra/scripts/init-secrets.ps1
docker compose up --build
```

Linux/macOS (mesma coisa, script equivalente):

```bash
cp .env.example .env
./infra/scripts/init-secrets.sh
docker compose up --build
```

A aplicação ficará disponível em <http://127.0.0.1:5173>. O frontend encaminha `/api`, `/admin`, `/account` e `/static` ao backend dentro da rede Docker — o backend e o PostgreSQL não publicam portas próprias no host.

Para validar a configuração sem iniciar os serviços:

```powershell
docker compose config --quiet
```

## Migrações e dados de demonstração

Com os containers em execução:

```powershell
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_catalog
```

`seed_catalog` popula o catálogo com produtos fictícios (é seguro rodar de novo; ele atualiza em vez de duplicar).

## Criando um usuário administrador

```powershell
docker compose exec backend python manage.py createsuperuser
```

Contas de staff/superusuário exigem MFA (TOTP) para acessar `/admin/`. Primeiro acesso:

1. Acesse <http://127.0.0.1:5173/account/login/> e entre com usuário e senha.
2. Você será direcionado a configurar o segundo fator. Escaneie o QR code com qualquer aplicativo autenticador TOTP (Google Authenticator, Microsoft Authenticator, Authy, 1Password, Bitwarden etc.) — não precisa ser um app específico, o padrão é aberto (RFC 6238). O nome que aparece no app é só um rótulo (`LustreDecor: <usuário>`), não precisa ser o nome real.
3. Confirme com o código de 6 dígitos gerado pelo app.
4. A partir daí, todo login em `/admin/` pede usuário, senha e o código do app.

Guarde os códigos de backup exibidos na configuração — eles permitem entrar caso perca acesso ao autenticador.

## Alertas de segurança

Além do log estruturado (todo evento de segurança já cai no `stdout` em JSON), os dois eventos mais acionáveis também disparam um e-mail: bloqueio por força bruta no login e tentativa de um cliente acessar carrinho/pedido de outro usuário. Por padrão o e-mail vai para o [Mailpit](https://mailpit.axllent.org/) local (sobe junto com `docker compose up`, sem precisar de credencial SMTP de verdade) — a interface fica em <http://127.0.0.1:8025>.

Para os alertas saírem de fato, defina `DJANGO_ADMINS` no seu `.env` (formato `Nome:email@exemplo.com`, pode ter mais de um separado por vírgula). Sem isso configurado, o alerta simplesmente não é enviado — o resto da aplicação funciona normalmente.

## Perfil de produção local (Nginx + ModSecurity/OWASP CRS + Gunicorn + TLS)

O dia a dia de desenvolvimento usa o Vite (hot-reload, sem TLS). Para rodar mais perto do desenho final — um único container (`waf`) servindo o frontend compilado, terminando TLS, fazendo proxy reverso e filtrando toda requisição por um WAF (ModSecurity + OWASP Core Rule Set), mais o backend via Gunicorn, sem o servidor de desenvolvimento do Django:

```powershell
docker compose -f docker-compose.prod.yml up --build
```

A aplicação fica em <https://127.0.0.1:8443> (a porta 8080 só redireciona para lá). As migrações e o `collectstatic` rodam automaticamente na inicialização do backend; para criar admin/popular o catálogo, use os mesmos comandos acima trocando `docker compose` por `docker compose -f docker-compose.prod.yml`. Backend e PostgreSQL continuam sem porta publicada.

O WAF bloqueia (403) requisições que pareçam SQLi, XSS, path traversal e outros padrões genéricos de ataque, com nível de paranoia 1 (o padrão recomendado pelo próprio CRS — mais alto significa mais regras ativas e mais chance de falso positivo). Para ajustar, defina `WAF_PARANOIA` no `.env` (1 a 4) antes de subir o perfil.

### TLS local

O certificado é autoassinado — o navegador vai mostrar um aviso de "conexão não segura" na primeira visita. Isso é esperado: clique em "Avançado" → "Prosseguir mesmo assim" (o texto exato varia por navegador).

Para gerar (ou renovar, ele expira em ~825 dias) o certificado:

```powershell
./infra/scripts/generate-tls-cert.ps1 127.0.0.1
```

```bash
./infra/scripts/generate-tls-cert.sh 127.0.0.1
```

Os arquivos ficam em `secrets/tls/` (fora do Git, como os demais segredos). **Todo** endereço usado pra acessar a aplicação — IP, hostname, `127.0.0.1` — vai só no `SAN` (Subject Alternative Name) do certificado, nunca no `CN`: o `CN` gerado é um rótulo genérico (`LustreDecor`), porque navegadores e clientes HTTP modernos validam pelo SAN, não pelo CN (RFC 6125) — certificado que depende do CN pro endereço é rejeitado. Os scripts já cuidam disso — aceitam mais de um endereço (`./generate-tls-cert.sh 192.168.9.34`) e sempre incluem `127.0.0.1`/`localhost` no SAN, além do que for passado.

Decisão do laboratório (sem domínio público, então nem Let's Encrypt nem qualquer outra CA pública servem): certificado **autoassinado ou emitido por uma CA interna** do laboratório, sempre com o IP real no SAN. Se a equipe já tiver uma CA interna própria, é só substituir `secrets/tls/localhost.{crt,key}` pelo par emitido por ela — a aplicação não distingue a origem do certificado, só exige que o SAN bata com o endereço acessado.

## Publicando na rede do laboratório

Por padrão tudo aqui só escuta em `127.0.0.1` — de propósito, pra não expor nada sem querer enquanto se desenvolve. Pra publicar o perfil de produção local na VM do laboratório (`192.168.9.34`, DMZ — `ep137-pucpr`), ajuste o `.env` antes de subir:

```env
WAF_BIND_HOST=192.168.9.34
WAF_EXTRA_HOST=192.168.9.34:8443
DJANGO_ALLOWED_HOSTS=192.168.9.34,localhost,127.0.0.1,backend
DJANGO_CORS_ALLOWED_ORIGINS=https://192.168.9.34:8443
DJANGO_CSRF_TRUSTED_ORIGINS=https://192.168.9.34:8443
```

E gere o certificado já com esse IP no SAN (seção acima) antes de subir:

```bash
./infra/scripts/generate-tls-cert.sh 192.168.9.34
docker compose -f docker-compose.prod.yml up -d --build
```

Sem `WAF_EXTRA_HOST` configurado, o `waf` responde `400` pra qualquer requisição que chegue com esse IP no cabeçalho `Host` (é a allowlist contra Host header injection — ver `docs/security.md`). Sem `DJANGO_CSRF_TRUSTED_ORIGINS`, formulários que alteram estado falham o CSRF silenciosamente. As duas variáveis têm que apontar pro mesmo endereço usado no navegador.

### Duas VMs (WAF na DMZ, backend na rede interna)

O acima assume `waf` e `backend` no mesmo host. Pra topologia real do laboratório — `waf` na VM da DMZ (`192.168.9.34`, `ep137-pucpr`) e `backend`/`postgres`/`mailpit` na VM da rede interna (`192.168.9.50`, `ep138-pucpr`), com pfSense entre as duas — use os dois arquivos dedicados em vez do `docker-compose.prod.yml`:

- **`docker-compose.dmz.yml`** (na VM da DMZ): só o `waf`, `docker compose` normal. `BACKEND_UPSTREAM` já aponta pro IP do backend na rede interna.
- **`docker-stack.interna.yml`** (na VM interna): `backend` + `postgres` + `mailpit`, formato **Swarm** (`docker stack deploy`), não `docker compose` — os comentários no topo do arquivo explicam as diferenças reais (sem `build:`, sem `depends_on`, secrets vindos do Swarm).

Os dois arquivos têm os valores de rede (IPs, portas, allowlist) fixos no próprio arquivo, não via `.env` — evita o mesmo problema de `.env` compartilhado entre perfis descrito acima. O parâmetro que conecta os dois é `BACKEND_UPSTREAM`, usado em `nginx/templates/conf.d/default.conf.template` pra decidir pra onde o `waf` faz proxy (`backend:8000` por padrão nos perfis de host único; o IP real da outra VM nesta topologia).

`/static/` (CSS/JS do Django Admin e da tela de MFA) não depende de volume compartilhado — o backend serve os próprios estáticos via [WhiteNoise](https://whitenoise.readthedocs.io/), e o `waf` só faz `proxy_pass` pra ele, igual às outras rotas. Funciona igual com os dois no mesmo host ou em VMs separadas.

## Testes

```powershell
docker compose run --rm backend pytest
```

```powershell
docker compose run --rm frontend npm run build
docker compose run --rm frontend npm run lint
```

## Principais endpoints da API (`/api/v1/`)

| Método | Rota | Acesso |
|---|---|---|
| GET | `/products/`, `/products/{id}/` | Público |
| GET | `/auth/csrf/` | Público (define cookie CSRF) |
| POST | `/auth/register/`, `/auth/login/` | Público (login com throttling) |
| POST | `/auth/logout/` | Autenticado |
| GET | `/auth/me/` | Autenticado |
| GET/POST | `/cart/`, `/cart/items/` | Cliente autenticado, dono do carrinho |
| PATCH/DELETE | `/cart/items/{id}/` | Dono do carrinho |
| GET/POST | `/orders/` | Cliente autenticado |
| GET | `/orders/{id}/` | Dono do pedido |
| GET | `/health/` | Interno/monitoramento |

## Segredos

O arquivo `.env` contém somente configuração local não sensível. O script `init-secrets` (`.ps1` no Windows, `.sh` em Linux/macOS — mesma lógica, nunca sobrescreve um segredo já existente) cria valores aleatórios em `secrets/` (chave do Django, senha do papel dono do banco e senha do papel de execução restrito), que está ignorado pelo Git. O Compose monta esses arquivos em `/run/secrets`; eles nunca são incorporados às imagens.

Docker Compose Secrets protege a entrega ao container, mas os arquivos de origem continuam sendo arquivos locais. Em produção, sua origem deverá ser um gerenciador de segredos apropriado à plataforma.

## Documentação

- [Arquitetura](docs/architecture.md)
- [Decisões de segurança](docs/security.md)
