from django.contrib import admin
from .models import Instructor, SolicitudRegistroProfesor


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'documento', 'especialidad', 'activo')
    search_fields = ('user__username', 'user__first_name',
                     'user__last_name', 'documento')
    list_filter = ('activo',)


@admin.register(SolicitudRegistroProfesor)
class SolicitudRegistroProfesorAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'nombres', 'apellidos', 'documento', 'especialidad', 'estado',
        'creado',
    )
    search_fields = (
        'nombres', 'apellidos', 'documento', 'usuario_solicitado', 'correo',
    )
    list_filter = ('estado', 'especialidad')
    readonly_fields = ('password_hash', 'creado', 'actualizado')
