from django.urls import path

from . import views


app_name = 'tienda'

urlpatterns = [
    path('', views.panel, name='panel'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('cuentas/nueva/', views.cuenta, name='crear_cuenta'),
    path('cuentas/<int:cuenta_id>/editar/', views.cuenta, name='editar_cuenta'),
    path('cuentas/<int:cuenta_id>/estado/', views.cambiar_estado_cuenta, name='cambiar_estado_cuenta'),
    path('categorias/nueva/', views.categoria, name='crear_categoria'),
    path('categorias/<int:categoria_id>/editar/', views.categoria, name='editar_categoria'),
    path('categorias-contables/nueva/', views.categoria_contable, name='crear_categoria_contable'),
    path('categorias-contables/<int:categoria_id>/editar/', views.categoria_contable, name='editar_categoria_contable'),
    path('subcategorias/nueva/', views.subcategoria, name='crear_subcategoria'),
    path('subcategorias/<int:subcategoria_id>/editar/', views.subcategoria, name='editar_subcategoria'),
    path('marcas/nueva/', views.marca_producto, name='crear_marca'),
    path('marcas/<int:marca_id>/editar/', views.marca_producto, name='editar_marca'),
    path('lineas-modelos/nueva/', views.linea_modelo_producto, name='crear_linea_modelo'),
    path('lineas-modelos/<int:linea_id>/editar/', views.linea_modelo_producto, name='editar_linea_modelo'),
    path('catalogos/lineas-modelos/', views.lineas_modelos_por_marca, name='lineas_modelos_por_marca'),
    path('disciplinas-producto/nueva/', views.disciplina_producto, name='crear_disciplina_producto'),
    path('disciplinas-producto/<int:disciplina_id>/editar/', views.disciplina_producto, name='editar_disciplina_producto'),
    path('clientes/nuevo/', views.cliente, name='crear_cliente'),
    path('clientes/<int:cliente_id>/editar/', views.cliente, name='editar_cliente'),
    path('productos/nuevo/', views.producto, name='crear_producto'),
    path('productos/<int:producto_id>/editar/', views.producto, name='editar_producto'),
    path(
        'productos/<int:producto_id>/estado/',
        views.cambiar_estado_producto,
        name='cambiar_estado_producto',
    ),
    path('ventas/nueva/', views.registrar_venta, name='registrar_venta'),
    path('ventas/<int:venta_id>/', views.detalle_venta, name='detalle_venta'),
    path('ventas/<int:venta_id>/comprobante.pdf', views.descargar_comprobante, name='descargar_comprobante'),
    path('ventas/<int:venta_id>/enviar-correo/', views.enviar_comprobante_correo, name='enviar_comprobante_correo'),
    path('ventas/<int:venta_id>/abono/', views.registrar_abono, name='registrar_abono'),
    path('ventas/<int:venta_id>/paz-y-salvo/', views.paz_y_salvo, name='paz_y_salvo'),
    path('creditos/', views.creditos, name='creditos'),
    path(
        'creditos/cartera-inicial/nueva/',
        views.registrar_cartera_inicial,
        name='registrar_cartera_inicial',
    ),
    path('compras/nueva/', views.registrar_compra, name='registrar_compra'),
    path('gastos/nuevo/', views.registrar_gasto, name='registrar_gasto'),
    path('ingresos/nuevo/', views.registrar_ingreso, name='registrar_ingreso'),
    path('transferencias/nueva/', views.registrar_transferencia, name='registrar_transferencia'),
    path('inventario/ajustar/', views.ajustar_inventario, name='ajustar_inventario'),
    path('consultas/', views.consultas, name='consultas'),
]
