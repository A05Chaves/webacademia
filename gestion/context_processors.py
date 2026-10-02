from .models import BilleteraMonedas


def gamificacion_usuario(request):
    if not request.user.is_authenticated:
        return {}
    billetera, _ = BilleteraMonedas.objects.get_or_create(usuario=request.user)
    return {'billetera_monedas_usuario': billetera}
