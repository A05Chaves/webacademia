from django.contrib import admin
from .models import ClaseProgramada, AsistenciaClase


@admin.register(ClaseProgramada)
class ClaseProgramadaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'dia',
        'hora_inicio',
        'hora_fin',
        'disciplina',
        'instructor',
        'cupo_maximo',
        'activa',
    )
    list_filter = ('dia', 'disciplina', 'activa')
    search_fields = (
        'disciplina',
        'instructor__user__first_name',
        'instructor__user__last_name',
    )


@admin.register(AsistenciaClase)
class AsistenciaClaseAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'alumno',
        'clase',
        'fecha_clase',
        'fecha_confirmacion',
        'estado',
    )
    list_filter = ('estado', 'fecha_clase')
    search_fields = (
        'alumno__user__first_name',
        'alumno__user__last_name',
        'alumno__documento',
    )
