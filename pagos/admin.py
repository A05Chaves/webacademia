from django.contrib import admin
from .models import (
    AcademiaCompetidora, AplicacionPromocion, CategoriaEvento, Evento,
    InscripcionEvento, MetodoPagoQR, Pago, Promocion,
)


@admin.register(MetodoPagoQR)
class MetodoPagoQRAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nombre',
        'titular',
        'cuenta_financiera',
        'activo',
    )
    search_fields = ('nombre', 'titular')
    list_filter = ('activo', 'cuenta_financiera')


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'tipo',
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
        'alumno__documento_acudiente',
        'pagador_documento',
        'pagador_nombre',
        'referencia_pago',
    )
    list_filter = ('tipo', 'estado', 'posible_duplicado', 'metodo_qr', 'fecha_reporte')


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'plan', 'tipo_beneficio', 'fecha_inicio', 'fecha_fin', 'publicada_home', 'activa')
    list_filter = ('tipo_beneficio', 'publicada_home', 'activa')
    search_fields = ('nombre', 'descripcion', 'condiciones')


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'tipo', 'alcance_torneo', 'fecha_inicio', 'fecha_fin',
        'fecha_inicio_inscripcion', 'fecha_limite_inscripcion',
        'cupo_maximo', 'publicada_home', 'activo',
    )
    list_filter = ('tipo', 'alcance_torneo', 'publicada_home', 'activo')
    search_fields = ('nombre', 'descripcion', 'lugar')


@admin.register(CategoriaEvento)
class CategoriaEventoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'evento', 'tipo_categoria', 'genero', 'nivel', 'peso_minimo', 'peso_maximo', 'activa')
    list_filter = ('evento', 'tipo_categoria', 'genero', 'activa')


@admin.register(AcademiaCompetidora)
class AcademiaCompetidoraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'logo', 'activa', 'actualizada')
    search_fields = ('nombre',)


@admin.register(InscripcionEvento)
class InscripcionEventoAdmin(admin.ModelAdmin):
    list_display = (
        'evento', 'participante_nombre', 'participante_documento',
        'academia_origen', 'categoria_evento', 'fecha_firma', 'estado', 'pago',
    )
    list_filter = ('estado', 'evento')
    search_fields = ('participante_nombre', 'participante_documento', 'acudiente_documento', 'correo')


admin.site.register(AplicacionPromocion)
