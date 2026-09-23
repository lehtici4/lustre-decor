from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice


def login_with_mfa(client, user):
    """Equivalente ao client.force_login(), mas com a sessão já marcada como
    verificada pelo segundo fator (como fica depois de /auth/mfa/verify/)."""
    device, _ = TOTPDevice.objects.get_or_create(user=user, name="teste", defaults={"confirmed": True})
    client.force_login(user)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return device
