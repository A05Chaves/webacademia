from django.contrib import admin

from .models import AjusteInventario, CuentaTienda, MovimientoTienda, ProductoTienda


@admin.register(CuentaTienda)
class CuentaTiendaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'saldo_inicial', 'activa')
    list_filter = ('tipo', 'activa')
    search_fields = ('nombre',)


@admin.register(ProductoTienda)
class ProductoTiendaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'referencia', 'precio_venta', 'costo_unitario',
        'stock', 'stock_minimo', 'activo',
    )
    list_filter = ('activo',)
    search_fields = ('nombre', 'referencia')


@admin.register(MovimientoTienda)
class MovimientoTiendaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'origen', 'tipo', 'cuenta', 'concepto', 'valor')
    list_filter = ('tipo', 'origen', 'cuenta', 'fecha')
    search_fields = ('concepto', 'observaciones')


@admin.register(AjusteInventario)
class AjusteInventarioAdmin(admin.ModelAdmin):
    list_display = (
        'fecha', 'producto', 'tipo', 'cantidad',
        'stock_anterior', 'stock_nuevo',
    )
    list_filter = ('tipo', 'fecha')
    search_fields = ('producto__nombre', 'motivo')
