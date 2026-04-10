from django.contrib import admin
from .models import MetodoPagoQR, Pago


@admin.register(MetodoPagoQR)
class MetodoPagoQRAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'titular', 'activo')
    search_fields = ('nombre', 'titular')
    list_filter = ('activo',)


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'alumno',
        'suscripcion',
        'metodo_qr',
        'valor',
        'estado',
        'fecha_reporte',
        'fecha_validacion',
        'validado_por',
    )
    search_fields = (
        'alumno__user__username',
        'alumno__user__first_name',
        'alumno__user__last_name',
        'alumno__documento',
        'referencia_pago',
    )
    list_filter = ('estado', 'metodo_qr', 'fecha_reporte')