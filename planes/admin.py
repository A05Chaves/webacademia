from django.contrib import admin
from .models import Plan, Suscripcion


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'precio', 'duracion_dias', 'activo')
    search_fields = ('nombre',)
    list_filter = ('activo',)


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ('id', 'alumno', 'plan', 'fecha_inicio', 'fecha_vencimiento', 'estado')
    search_fields = (
        'alumno__user__username',
        'alumno__user__first_name',
        'alumno__user__last_name',
        'plan__nombre',
    )
    list_filter = ('estado', 'plan')
