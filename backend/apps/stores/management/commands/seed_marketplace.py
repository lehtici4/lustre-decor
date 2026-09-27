"""Popula o marketplace com 3 lojas parceiras fictícias, cada uma com 5
produtos, uma vitrine temática e um usuário parceiro.

    python manage.py seed_marketplace                    # idempotente
    python manage.py seed_marketplace --reset-passwords  # gera senhas novas

Senhas dos parceiros: geradas aleatoriamente e mostradas UMA vez no terminal
(na criação ou com --reset-passwords) — nunca ficam no código. No primeiro
login cada parceiro cadastra o próprio TOTP (MFA obrigatório).
"""

import secrets

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.roles import CLIENTE, PARCEIRO
from apps.catalog.models import Product
from apps.stores.models import Campaign, Store

IMG = "/products/marketplace/"

STORES = [
    {
        "name": "Ateliê Terra",
        "partner": ("parceiro.terra", "terra@lustredecor.local"),
        "products": [
            ("Jarra de Barro Esmaltada", "Jarra modelada à mão em barro vermelho, esmalte translúcido.", "139.90", "jarra-barro-esmaltada.svg"),
            ("Conjunto de Pratos Artesanais", "Quatro pratos rasos de cerâmica com borda irregular.", "229.00", "pratos-artesanais.svg"),
            ("Castiçal de Cerâmica Rústica", "Castiçal de cerâmica queimada, para velas de 2 cm.", "79.90", "castical-ceramica.svg"),
            ("Bowl Decorativo Azul Anil", "Bowl de cerâmica com esmalte azul anil e interior claro.", "99.00", "bowl-azul-anil.svg"),
            ("Moringa Tradicional", "Moringa de barro que mantém a água fresca, feita no torno.", "119.90", "moringa-tradicional.svg"),
        ],
        "campaign": {
            "name": "Cerâmica de Primavera",
            "slug": "ceramica-de-primavera",
            "description": "Peças de barro e esmaltes claros para uma mesa leve e florida.",
            "accent_color": "#b5562f",
            "products": 4,
        },
    },
    {
        "name": "Casa Boho Fibras",
        "partner": ("parceiro.boho", "boho@lustredecor.local"),
        "products": [
            ("Luminária Pendente de Rattan", "Cúpula de rattan natural trançado, 45 cm de diâmetro.", "289.00", "luminaria-rattan.svg"),
            ("Tapete de Juta Trançado", "Tapete de juta 1,5 x 2 m, trama grossa e bordas costuradas.", "399.00", "tapete-juta.svg"),
            ("Cesto de Palha com Alças", "Cesto de palha de milho com alças, para plantas ou mantas.", "89.90", "cesto-palha-alcas.svg"),
            ("Macramê de Parede Aurora", "Painel de macramê em algodão cru, 60 x 90 cm.", "149.00", "macrame-aurora.svg"),
            ("Pufe de Seagrass", "Pufe baixo em fibra de seagrass, estrutura firme.", "259.00", "pufe-seagrass.svg"),
        ],
        "campaign": {
            "name": "Refúgio Boho",
            "slug": "refugio-boho",
            "description": "Fibras naturais, texturas e tons de areia para uma sala acolhedora.",
            "accent_color": "#8a7a3b",
            "products": 4,
        },
    },
    {
        "name": "Luz & Metal Studio",
        "partner": ("parceiro.luz", "luz@lustredecor.local"),
        "products": [
            ("Luminária de Piso Arco Latão", "Luminária de piso em arco, haste de latão e base de mármore.", "699.00", "luminaria-arco-latao.svg"),
            ("Arandela Industrial Preta", "Arandela de parede em aço preto fosco com cúpula orientável.", "219.00", "arandela-industrial.svg"),
            ("Lanterna Marroquina Vazada", "Lanterna de metal vazado que projeta desenhos de luz.", "169.00", "lanterna-marroquina.svg"),
            ("Espelho Sol Dourado", "Espelho decorativo com raios metálicos dourados, 70 cm.", "329.00", "espelho-sol.svg"),
            ("Bandeja Espelhada de Latão", "Bandeja com fundo espelhado e alças de latão.", "189.90", "bandeja-espelhada.svg"),
        ],
        "campaign": {
            "name": "Noites Aconchegantes",
            "slug": "noites-aconchegantes",
            "description": "Luz quente e metais dourados para as noites em casa.",
            "accent_color": "#3d4a5c",
            "products": 3,
        },
    },
]


class Command(BaseCommand):
    help = "Cria 3 lojas parceiras fictícias com produtos, vitrines e usuários parceiros (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--reset-passwords", action="store_true", help="Gera senhas novas para os parceiros.")

    @transaction.atomic
    def handle(self, *args, **options):
        partner_group, _ = Group.objects.get_or_create(name=PARCEIRO)
        customer_group, _ = Group.objects.get_or_create(name=CLIENTE)
        credentials = []

        for spec in STORES:
            store, _ = Store.objects.get_or_create(name=spec["name"], defaults={"active": True})

            username, email = spec["partner"]
            user, created = User.objects.get_or_create(username=username, defaults={"email": email})
            if created or options["reset_passwords"]:
                password = secrets.token_urlsafe(12)
                user.set_password(password)
                user.save()
                credentials.append((store.name, username, password))
            user.groups.add(partner_group, customer_group)
            store.members.add(user)

            products = []
            for name, description, price, image in spec["products"]:
                product, _ = Product.objects.update_or_create(
                    name=name,
                    defaults={
                        "description": description,
                        "price": price,
                        "image_url": IMG + image,
                        "store": store,
                        "active": True,
                    },
                )
                products.append(product)

            camp = spec["campaign"]
            campaign, _ = Campaign.objects.update_or_create(
                slug=camp["slug"],
                defaults={
                    "store": store,
                    "name": camp["name"],
                    "description": camp["description"],
                    "accent_color": camp["accent_color"],
                    "active": True,
                },
            )
            campaign.products.set(products[: camp["products"]])

        self.stdout.write(self.style.SUCCESS(f"Marketplace populado: {len(STORES)} lojas, vitrines e produtos."))
        if credentials:
            self.stdout.write(self.style.WARNING("Senhas dos parceiros (mostradas só agora — anote em local seguro):"))
            for store_name, username, password in credentials:
                self.stdout.write(f"  {store_name:22} {username:16} {password}")
            self.stdout.write("No primeiro login cada parceiro cadastra o TOTP (MFA).")
