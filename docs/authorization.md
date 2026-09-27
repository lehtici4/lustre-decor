# Autorização — papéis (RBAC) e marketplace

Papéis implementados como **grupos do Django** (`apps/accounts/roles.py`), criados automaticamente a cada `migrate` (sinal `post_migrate`). Na Sprint 2, os papéis do Keycloak (OIDC) são mapeados para estes mesmos grupos — as checagens não mudam.

## Papéis

| Papel | Como se obtém | O que pode | MFA |
| --- | --- | --- | --- |
| **cliente** | automático no cadastro público | catálogo; carrinho e pedidos **próprios** | obrigatório |
| **parceiro** | administrador vincula o usuário a uma **Loja** no Django Admin | produtos e itens de pedido **da(s) própria(s) loja(s)**, via `/parceiro` | obrigatório |
| **administrador** | `is_staff` + grupo `administrador` (concedido por outro admin) | Django Admin: lojas, produtos, pedidos, usuários (sem apagar usuário) | obrigatório (Admin exige OTP) |
| **tester** | só a conta de avaliação `teste@pucparana.com` (`seed_test_user`) | **igual a cliente**, nada além | isenta |

## Regras de segurança

- **Ninguém se promove.** O cadastro público sempre cria `cliente`; campos extras no JSON (`is_staff`, `roles`) são ignorados. Parceiro e administrador só por concessão de um administrador (que entrou com MFA).
- **Conta isenta de MFA nunca é privilegiada.** Mesmo que alguém coloque a conta de teste no grupo `parceiro`/`administrador`, marque `is_staff` direto no banco ou a vincule a uma loja, `is_partner()`/`is_administrator()` retornam falso. O Admin também recusa salvar essa combinação (formulário de usuário e de loja).
- **Parceiro de fato** = grupo `parceiro` **e** ao menos uma loja **ativa** **e** sessão verificada por MFA. Desativar a loja corta o acesso imediatamente, sem mexer no usuário.
- **Isolamento por loja** em `apps/core/services/partner_service.py`: produto ou item de pedido de outra loja (ou da própria Lustre Decor) responde **404** e gera log `forbidden_object_access` — o mesmo evento que já dispara alerta por e-mail.
- **Mínimo de dados do cliente para o parceiro:** o parceiro vê pedido, data, item, quantidade, preço e status de envio — **não** vê username/e-mail do comprador nem itens de outras lojas no mesmo pedido.
- Produto de parceiro: preço > 0; `image_url` só caminho local (`/...`) ou `https://` (bloqueia `javascript:`/`data:`). Sem DELETE — o parceiro **oculta** o produto (`active=false`), porque produtos já vendidos são referenciados por pedidos.
- Loja inativa: produtos somem do catálogo e não podem ser adicionados ao carrinho.

## Modelo de dados

- `stores.Store` (`name`, `active`, `members` → usuários parceiros).
- `catalog.Product.store` — vazio = produto da própria Lustre Decor (só o administrador gerencia).
- `orders.OrderItem.store` (snapshot da loja na compra) e `fulfillment_status` (`pending` → `shipped`).

## API do parceiro (`/api/v1/partner/`, exige papel parceiro)

| Método | Rota | Uso |
| --- | --- | --- |
| GET | `stores/` | lojas do parceiro |
| GET, POST | `products/` | listar / cadastrar produto (só em loja própria) |
| GET, PATCH | `products/<id>/` | editar preço, descrição, imagem, publicar/ocultar |
| GET | `order-items/` | itens vendidos pelas lojas do parceiro |
| PATCH | `order-items/<id>/` | `{"fulfillment_status": "shipped"}` (demais campos são somente leitura) |

| GET, POST | `campaigns/` | listar / criar vitrine (só com produtos da própria loja) |
| GET, PATCH | `campaigns/<id>/` | editar, publicar/pausar vitrine |

`GET /api/v1/auth/me/` passa a devolver `roles` e `is_partner`.

## Vitrines temáticas (campanhas)

Cada loja pode ter vitrines (`stores.Campaign`): nome, texto, cor de destaque (`#RRGGBB`, validada no backend e no frontend) e uma seleção de produtos **da própria loja** (validado na API do parceiro e no Admin). Não mexem em preço. Aparecem na home e em `/vitrines/<slug>` quando: ativa, loja ativa, dentro do período (`starts_at`/`ends_at`, opcionais) e com ao menos um produto visível. API pública: `GET /api/v1/campaigns/` e `GET /api/v1/campaigns/<slug>/`.

## Dados de demonstração

```bash
docker exec $(docker ps -qf name=lustre_decor_backend) python manage.py seed_marketplace
```

Cria (idempotente) 3 lojas — **Ateliê Terra** (cerâmica, vitrine *Cerâmica de Primavera*), **Casa Boho Fibras** (fibras, *Refúgio Boho*) e **Luz & Metal Studio** (iluminação/metais, *Noites Aconchegantes*) — com 5 produtos cada (imagens em `frontend/public/products/marketplace/`) e um usuário parceiro por loja (`parceiro.terra`, `parceiro.boho`, `parceiro.luz`). As senhas são aleatórias e aparecem **só uma vez** no terminal; `--reset-passwords` gera novas. Cada parceiro cadastra o TOTP no primeiro login.

## Operação (Django Admin, com MFA)

- **Tornar alguém parceiro:** *Lojas parceiras › Lojas* → criar/editar a loja → adicionar o usuário em *parceiros* → salvar (o grupo `parceiro` é adicionado automaticamente).
- **Tirar o acesso de um parceiro:** remover o usuário da loja, ou desativar a loja.
- **Criar administrador:** *Usuários* → marcar *Membro da equipe* + grupo `administrador`. Ele cadastra o TOTP no primeiro login da loja (mesmo app autenticador); depois entra no Admin por `/account/login/` com senha + código.

Testes: `backend/tests/test_roles_marketplace.py` (papéis, travas da conta isenta, isolamento entre lojas, catálogo e despacho) e `backend/tests/test_campaigns.py` (vitrines e seed).
