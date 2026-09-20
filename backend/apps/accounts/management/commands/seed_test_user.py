from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Cria usuário de teste obrigatório para avaliação (idempotente)"

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            email="teste@pucparana.com",
            defaults={"username": "teste@pucparana.com"},
        )
        user.set_password("Teste@2026")
        user.is_staff = False
        user.is_active = True
        user.save()

        user.groups.clear()

        status = "criado" if created else "atualizado"
        self.stdout.write(self.style.SUCCESS(f"Usuário de teste {status}."))
