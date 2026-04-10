from django.contrib import admin
from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'usuario',
        'tipo',
        'titulo',
        'canal',
        'estado',
        'fecha_programada',
        'fecha_envio',
    )
    search_fields = (
        'usuario__username',
        'usuario__first_name',
        'usuario__last_name',
        'titulo',
        'mensaje',
    )
    list_filter = ('tipo', 'canal', 'estado')