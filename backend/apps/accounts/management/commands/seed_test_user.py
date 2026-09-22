from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django_otp import devices_for_user


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

        # Conta de avaliação fica SEM MFA (ver MFA_EXEMPT_USERS em
        # config/settings/base.py): remove qualquer dispositivo OTP que tenha
        # sobrado de um teste anterior, para o login seguir só com senha.
        for device in devices_for_user(user, confirmed=None):
            device.delete()

        if user.username.lower() not in {name.lower() for name in settings.MFA_EXEMPT_USERS}:
            self.stdout.write(
                self.style.WARNING(
                    "Atenção: esta conta NÃO está em MFA_EXEMPT_USERS — o login vai exigir TOTP."
                )
            )

        status = "criado" if created else "atualizado"
        self.stdout.write(self.style.SUCCESS(f"Usuário de teste {status}."))
