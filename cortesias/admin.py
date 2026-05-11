from django.contrib import admin
from .models import ConsentimientoFirmado, ClaseCortesia


@admin.register(ConsentimientoFirmado)
class ConsentimientoFirmadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_estudiante', 'tipo', 'fecha_firma')
    search_fields = ('nombre_estudiante', 'documento_estudiante')
    list_filter = ('tipo',)


@admin.register(ClaseCortesia)
class ClaseCortesiaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombres', 'apellidos', 'telefono',
                    'tipo_persona', 'clase', 'fecha_registro')
    search_fields = ('nombres', 'apellidos', 'documento', 'telefono')
    list_filter = ('tipo_persona', 'fecha_registro')
