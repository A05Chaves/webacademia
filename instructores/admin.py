from django.contrib import admin
from .models import Instructor


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'documento', 'especialidad', 'activo')
    search_fields = ('user__username', 'user__first_name',
                     'user__last_name', 'documento')
    list_filter = ('activo',)
