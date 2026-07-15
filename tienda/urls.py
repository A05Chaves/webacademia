from django.urls import path

from . import views


app_name = 'tienda'

urlpatterns = [
    path('', views.panel, name='panel'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('cuentas/nueva/', views.cuenta, name='crear_cuenta'),
    path('cuentas/<int:cuenta_id>/editar/', views.cuenta, name='editar_cuenta'),
    path('productos/nuevo/', views.producto, name='crear_producto'),
    path('productos/<int:producto_id>/editar/', views.producto, name='editar_producto'),
    path(
        'productos/<int:producto_id>/estado/',
        views.cambiar_estado_producto,
        name='cambiar_estado_producto',
    ),
    path('ventas/nueva/', views.registrar_venta, name='registrar_venta'),
    path('compras/nueva/', views.registrar_compra, name='registrar_compra'),
    path('gastos/nuevo/', views.registrar_gasto, name='registrar_gasto'),
    path('inventario/ajustar/', views.ajustar_inventario, name='ajustar_inventario'),
]
