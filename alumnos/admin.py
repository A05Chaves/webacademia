from django.contrib import admin
from .models import Alumno


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'documento', 'disciplina', 'grado', 'estado')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'documento')
    list_filter = ('disciplina', 'estado')