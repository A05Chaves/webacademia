from django.contrib import admin
from .models import RegistroLegalEstudiante


@admin.register(RegistroLegalEstudiante)
class RegistroLegalEstudianteAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nombres',
        'apellidos',
        'documento',
        'usuario_solicitado',
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
        'usuario_solicitado',
        'correo',
        'celular',
    )

    readonly_fields = (
        # Aprobar desde el campo de estado solo cambia el registro legal y no
        # crea la ficha del alumno. La aprobación debe hacerse desde el flujo
        # de revisión de la aplicación.
        'estado',
        'texto_consentimiento',
        'firma_base64',
        'fecha_firma',
        'ip_firma',
        'creado',
        'actualizado',
    )
