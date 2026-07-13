from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario

    list_display = ('id', 'username', 'username_modificado', 'first_name', 'last_name', 'email', 'telefono', 'rol', 'is_active')
    list_filter = ('rol', 'is_active', 'is_staff', 'is_superuser')

    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {
            'fields': ('telefono', 'rol', 'username_modificado')
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información adicional', {
            'fields': ('first_name', 'last_name', 'email', 'telefono', 'rol')
        }),
    )

    search_fields = ('username', 'first_name', 'last_name', 'email', 'telefono')
    ordering = ('username',)
