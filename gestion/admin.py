from django.contrib import admin
from .models import ConfiguracionHome
# Register your models here.


@admin.register(ConfiguracionHome)
class ConfiguracionHomeAdmin(admin.ModelAdmin):
    list_display = (
        'video_promo_url',
        'playlist_youtube_url',
        'activo',
        'actualizado',
    )
