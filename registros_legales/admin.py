from django.contrib import admin
from .models import RegistroLegalEstudiante


@admin.register(RegistroLegalEstudiante)
class RegistroLegalEstudianteAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nombres',
        'apellidos',
        'documento',
        'tipo_estudiante',
        'estado',
        'fecha_firma',
        'creado',
    )

    list_filter = (
        'tipo_estudiante',
        'estado',
        'fecha_firma',
    )

    search_fields = (
        'nombres',
        'apellidos',
        'documento',
        'correo',
        'celular',
    )

    readonly_fields = (
        'texto_consentimiento',
        'firma_base64',
        'fecha_firma',
        'ip_firma',
        'creado',
        'actualizado',
    )
