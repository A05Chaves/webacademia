from django.contrib import admin
from .models import (
    BilleteraMonedas, ConfiguracionClases, ConfiguracionHome,
    MovimientoMonedas, RecompensaOtorgada, TipoRecompensa,
)
# Register your models here.


@admin.register(ConfiguracionHome)
class ConfiguracionHomeAdmin(admin.ModelAdmin):
    list_display = (
        'video_promo_url',
        'playlist_youtube_url',
        'activo',
        'actualizado',
    )


@admin.register(ConfiguracionClases)
class ConfiguracionClasesAdmin(admin.ModelAdmin):
    list_display = (
        'minutos_antes_confirmacion', 'minutos_despues_confirmacion',
        'gamificacion_activa', 'monedas_por_asistencia',
        'monedas_por_asistencia_profesor', 'actualizado',
    )


@admin.register(BilleteraMonedas)
class BilleteraMonedasAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'avatar', 'saldo', 'actualizada')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name')
    readonly_fields = ('usuario', 'avatar', 'saldo', 'creada', 'actualizada')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MovimientoMonedas)
class MovimientoMonedasAdmin(admin.ModelAdmin):
    list_display = (
        'creado', 'billetera', 'tipo', 'cantidad', 'saldo_resultante', 'asistencia',
    )
    list_filter = ('tipo', 'creado')
    search_fields = (
        'billetera__usuario__username', 'billetera__usuario__first_name',
        'billetera__usuario__last_name', 'descripcion',
    )
    readonly_fields = (
        'billetera', 'asistencia', 'tipo', 'cantidad', 'saldo_resultante',
        'descripcion', 'creado', 'registrado_por', 'recompensa_otorgada',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TipoRecompensa)
class TipoRecompensaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'simbolo', 'valor_monedas', 'cantidad_para_bono',
        'monedas_bono', 'activa', 'orden',
    )
    list_filter = ('activa',)


@admin.register(RecompensaOtorgada)
class RecompensaOtorgadaAdmin(admin.ModelAdmin):
    list_display = (
        'creada', 'alumno', 'nombre_snapshot', 'monedas_otorgadas',
        'bono_otorgado', 'canjeada', 'otorgada_por',
    )
    list_filter = ('recompensa', 'canjeada', 'creada')
    search_fields = (
        'alumno__user__first_name', 'alumno__user__last_name',
        'alumno__documento', 'motivo',
    )
    readonly_fields = (
        'recompensa', 'alumno', 'asistencia', 'otorgada_por',
        'nombre_snapshot', 'simbolo_snapshot', 'imagen_snapshot',
        'monedas_otorgadas', 'bono_otorgado', 'motivo', 'canjeada',
        'canjeada_en', 'creada',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
