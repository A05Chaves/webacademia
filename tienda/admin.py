from django.contrib import admin

from .models import (
    AjusteInventario, AplicacionAbonoCuota, CategoriaProducto, ClienteTienda,
    CuentaTienda, CuotaVentaTienda, DetalleVentaTienda, MovimientoTienda, ProductoTienda,
    SubcategoriaProducto, VentaTienda,
)


@admin.register(CuentaTienda)
class CuentaTiendaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'moneda', 'saldo_inicial', 'activa')
    list_filter = ('tipo', 'moneda', 'activa')
    search_fields = ('nombre',)


@admin.register(ProductoTienda)
class ProductoTiendaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'referencia', 'color', 'talla', 'moneda', 'precio_venta', 'costo_unitario',
        'stock', 'stock_minimo', 'activo',
    )
    list_filter = ('activo', 'moneda', 'categoria', 'subcategoria')
    search_fields = ('nombre', 'referencia', 'codigo_barras')


@admin.register(MovimientoTienda)
class MovimientoTiendaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'origen', 'tipo', 'cuenta', 'moneda', 'concepto', 'valor')
    list_filter = ('tipo', 'origen', 'moneda', 'cuenta', 'fecha')
    search_fields = ('concepto', 'observaciones')


@admin.register(AjusteInventario)
class AjusteInventarioAdmin(admin.ModelAdmin):
    list_display = (
        'fecha', 'producto', 'tipo', 'cantidad',
        'stock_anterior', 'stock_nuevo',
    )
    list_filter = ('tipo', 'fecha')
    search_fields = ('producto__nombre', 'motivo')


admin.site.register(CategoriaProducto)
admin.site.register(SubcategoriaProducto)
admin.site.register(ClienteTienda)
admin.site.register(VentaTienda)
admin.site.register(DetalleVentaTienda)
admin.site.register(CuotaVentaTienda)
admin.site.register(AplicacionAbonoCuota)
