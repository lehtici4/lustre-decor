from django.core.management.base import BaseCommand

from apps.catalog.models import Product

# As imagens ficam em frontend/public/products/, servidas como arquivos estáticos
# pelo Vite/Nginx — sem upload, só referência simples, como pede a especificação
# do laboratório.
FICTITIOUS_PRODUCTS = [
    {
        "name": "Luminária de Mesa Âmbar",
        "description": "Luminária de mesa com cúpula em vidro âmbar e base em latão escovado.",
        "price": "189.90",
        "image_url": "/products/luminaria-mesa-ambar.webp",
    },
    {
        "name": "Vaso Cerâmico Terracota",
        "description": "Vaso decorativo em cerâmica artesanal, acabamento terracota fosco.",
        "price": "94.50",
        "image_url": "/products/vaso-ceramico-terracota.webp",
    },
    {
        "name": "Tapete Kilim Geométrico",
        "description": "Tapete tecido à mão com estampa geométrica em tons terrosos.",
        "price": "349.00",
        "image_url": "/products/tapete-kilim-geometrico.jpg",
    },
    {
        "name": "Espelho Redondo Dourado",
        "description": "Espelho de parede com moldura metálica dourada, 60cm de diâmetro.",
        "price": "259.90",
        "image_url": "/products/espelho-redondo-dourado.jpg",
    },
    {
        "name": "Almofada Linho Cru",
        "description": "Almofada decorativa em linho cru com enchimento antialérgico.",
        "price": "69.90",
        "image_url": "/products/almofada-linho-cru.webp",
    },
    {
        "name": "Cesto Organizador de Fibra Natural",
        "description": "Cesto trançado em fibra natural, ideal para organização de ambientes.",
        "price": "119.00",
        "image_url": "/products/cesto-fibra-natural.jpg",
    },
]


class Command(BaseCommand):
    help = "Popula o catálogo com produtos fictícios de demonstração."

    def handle(self, *args, **options):
        created = 0
        for data in FICTITIOUS_PRODUCTS:
            _, was_created = Product.objects.update_or_create(
                name=data["name"], defaults=data
            )
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo populado: {created} produto(s) criado(s), "
                f"{len(FICTITIOUS_PRODUCTS) - created} atualizado(s)."
            )
        )
