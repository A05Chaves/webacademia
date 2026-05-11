from django.contrib import admin
from .models import CuentaFinanciera, MovimientoFinanciero, PagoProgramado, CategoriaFinanciera


@admin.register(CuentaFinanciera)
class CuentaFinancieraAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'tipo', 'saldo_inicial', 'activa')
    list_filter = ('tipo', 'activa')
    search_fields = ('nombre',)


@admin.register(MovimientoFinanciero)
class MovimientoFinancieroAdmin(admin.ModelAdmin):
    list_display = ('id', 'cuenta', 'tipo', 'concepto',
                    'valor', 'fecha', 'pago')
    list_filter = ('tipo', 'cuenta', 'fecha')
    search_fields = ('concepto', 'observaciones')


@admin.register(PagoProgramado)
class PagoProgramadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'concepto', 'valor', 'fecha_vencimiento',
                    'estado', 'cuenta_pago', 'fecha_pago')
    list_filter = ('estado', 'cuenta_pago', 'fecha_vencimiento')
    search_fields = ('concepto', 'observaciones')


@admin.register(CategoriaFinanciera)
class CategoriaFinancieraAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'tipo', 'activa')
    list_filter = ('tipo', 'activa')
    search_fields = ('nombre',)
