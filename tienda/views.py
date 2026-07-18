from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AjusteInventarioForm,
    CompraTiendaForm,
    CuentaTiendaForm,
    GastoTiendaForm,
    ProductoTiendaForm,
    VentaTiendaForm,
)
from .models import AjusteInventario, CuentaTienda, MovimientoTienda, ProductoTienda


def _render_formulario(
    request,
    form,
    titulo,
    icono,
    texto_boton,
    clase_boton,
    volver_url='tienda:panel',
):
    return render(request, 'tienda/formulario.html', {
        'form': form,
        'titulo': titulo,
        'icono': icono,
        'texto_boton': texto_boton,
        'clase_boton': clase_boton,
        'volver_url': volver_url,
    })


@staff_member_required
def panel(request):
    hoy = timezone.localdate()
    cuentas = list(CuentaTienda.objects.all())
    for cuenta in cuentas:
        cuenta.saldo_calculado = cuenta.saldo_actual

    cuentas_activas = [cuenta for cuenta in cuentas if cuenta.activa]
    saldo_total = sum((cuenta.saldo_calculado for cuenta in cuentas_activas), 0)
    movimientos_mes = MovimientoTienda.objects.filter(
        fecha__year=hoy.year,
        fecha__month=hoy.month,
    )
    ventas_mes = movimientos_mes.filter(
        tipo=MovimientoTienda.Tipos.INGRESO,
        origen=MovimientoTienda.Origenes.VENTA,
    ).aggregate(total=Sum('valor'))['total'] or 0
    egresos_mes = movimientos_mes.filter(
        tipo=MovimientoTienda.Tipos.EGRESO,
    ).aggregate(total=Sum('valor'))['total'] or 0
    egresos_acumulados = MovimientoTienda.objects.filter(
        tipo=MovimientoTienda.Tipos.EGRESO,
    ).aggregate(total=Sum('valor'))['total'] or 0
    utilidad_mes = ventas_mes - egresos_mes

    productos = list(ProductoTienda.objects.all())
    valor_inventario = sum(
        (producto.valor_inventario for producto in productos if producto.activo),
        0,
    )
    productos_bajo_stock = [
        producto for producto in productos
        if producto.activo and producto.bajo_stock
    ]

    movimientos = MovimientoTienda.objects.select_related(
        'cuenta', 'producto', 'registrado_por'
    )[:12]

    nombres_meses = (
        'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
        'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
    )
    labels_flujo = []
    ventas_flujo = []
    egresos_flujo = []
    mes_actual_absoluto = hoy.year * 12 + hoy.month - 1
    for desplazamiento in range(5, -1, -1):
        mes_absoluto = mes_actual_absoluto - desplazamiento
        anio_flujo, indice_mes = divmod(mes_absoluto, 12)
        mes_flujo = indice_mes + 1
        labels_flujo.append(f'{nombres_meses[indice_mes]} {anio_flujo}')
        ventas = MovimientoTienda.objects.filter(
            tipo=MovimientoTienda.Tipos.INGRESO,
            origen=MovimientoTienda.Origenes.VENTA,
            fecha__year=anio_flujo,
            fecha__month=mes_flujo,
        ).aggregate(total=Sum('valor'))['total'] or 0
        egresos = MovimientoTienda.objects.filter(
            tipo=MovimientoTienda.Tipos.EGRESO,
            fecha__year=anio_flujo,
            fecha__month=mes_flujo,
        ).aggregate(total=Sum('valor'))['total'] or 0
        ventas_flujo.append(float(ventas))
        egresos_flujo.append(float(egresos))

    ventas_por_producto = MovimientoTienda.objects.filter(
        origen=MovimientoTienda.Origenes.VENTA,
        producto__isnull=False,
    ).values('producto__nombre').annotate(
        total=Sum('valor')
    ).order_by('-total')[:6]
    labels_productos = [
        item['producto__nombre'] for item in ventas_por_producto
    ]
    ventas_productos = [
        float(item['total']) for item in ventas_por_producto
    ]

    return render(request, 'tienda/panel.html', {
        'cuentas': cuentas,
        'productos': productos,
        'productos_bajo_stock': productos_bajo_stock,
        'movimientos': movimientos,
        'saldo_total': saldo_total,
        'ventas_mes': ventas_mes,
        'egresos_mes': egresos_mes,
        'egresos_acumulados': egresos_acumulados,
        'utilidad_mes': utilidad_mes,
        'valor_inventario': valor_inventario,
        'labels_flujo': labels_flujo,
        'ventas_flujo': ventas_flujo,
        'egresos_flujo': egresos_flujo,
        'labels_productos': labels_productos,
        'ventas_productos': ventas_productos,
    })


@staff_member_required
def configuracion(request):
    cuentas = list(CuentaTienda.objects.all())
    for cuenta_tienda in cuentas:
        cuenta_tienda.saldo_calculado = cuenta_tienda.saldo_actual
    productos = ProductoTienda.objects.all()
    return render(request, 'tienda/configuracion.html', {
        'cuentas': cuentas,
        'productos': productos,
    })


@staff_member_required
def cuenta(request, cuenta_id=None):
    instancia = None
    if cuenta_id is not None:
        instancia = get_object_or_404(CuentaTienda, id=cuenta_id)
    form = CuentaTiendaForm(request.POST or None, instance=instancia)
    if request.method == 'POST' and form.is_valid():
        guardada = form.save()
        messages.success(request, f'Cuenta "{guardada.nombre}" guardada correctamente.')
        return redirect('tienda:configuracion')
    titulo = 'Editar cuenta de tienda' if instancia else 'Nueva cuenta de tienda'
    return _render_formulario(
        request, form, titulo, 'fa-building-columns', 'Guardar cuenta',
        'btn-success', 'tienda:configuracion',
    )


@staff_member_required
def producto(request, producto_id=None):
    instancia = None
    if producto_id is not None:
        instancia = get_object_or_404(ProductoTienda, id=producto_id)
    form = ProductoTiendaForm(request.POST or None, instance=instancia)
    if request.method == 'POST' and form.is_valid():
        creando = instancia is None
        producto_guardado = form.save(commit=False)
        if creando:
            producto_guardado.stock = form.cleaned_data.get('stock_inicial') or 0
        producto_guardado.save()
        if creando and producto_guardado.stock:
            AjusteInventario.objects.create(
                producto=producto_guardado,
                tipo=AjusteInventario.Tipos.ENTRADA,
                cantidad=producto_guardado.stock,
                stock_anterior=0,
                stock_nuevo=producto_guardado.stock,
                motivo='Inventario inicial del producto.',
                registrado_por=request.user,
            )
        messages.success(
            request,
            f'Producto "{producto_guardado.nombre}" guardado correctamente.'
        )
        return redirect('tienda:configuracion')
    titulo = 'Editar producto' if instancia else 'Nuevo producto'
    return _render_formulario(
        request, form, titulo, 'fa-shirt', 'Guardar producto',
        'btn-success', 'tienda:configuracion',
    )


@staff_member_required
@require_POST
def cambiar_estado_producto(request, producto_id):
    producto_tienda = get_object_or_404(ProductoTienda, id=producto_id)
    producto_tienda.activo = not producto_tienda.activo
    producto_tienda.save(update_fields=['activo', 'actualizado'])
    estado = 'activado' if producto_tienda.activo else 'marcado como obsoleto'
    messages.success(request, f'Producto "{producto_tienda.nombre}" {estado}.')
    return redirect('tienda:configuracion')


@staff_member_required
def registrar_venta(request):
    form = VentaTiendaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            producto_tienda = ProductoTienda.objects.select_for_update().get(
                id=form.cleaned_data['producto'].id,
                activo=True,
            )
            cantidad = form.cleaned_data['cantidad']
            if cantidad > producto_tienda.stock:
                form.add_error(
                    'cantidad',
                    f'No hay inventario suficiente. Disponibles: {producto_tienda.stock}.',
                )
            else:
                total = producto_tienda.precio_venta * cantidad
                MovimientoTienda.objects.create(
                    cuenta=form.cleaned_data['cuenta'],
                    tipo=MovimientoTienda.Tipos.INGRESO,
                    origen=MovimientoTienda.Origenes.VENTA,
                    concepto=f'Venta - {producto_tienda.nombre}',
                    valor=total,
                    producto=producto_tienda,
                    cantidad=cantidad,
                    observaciones=form.cleaned_data['observaciones'],
                    registrado_por=request.user,
                )
                producto_tienda.stock -= cantidad
                producto_tienda.save(update_fields=['stock', 'actualizado'])
                messages.success(
                    request,
                    (
                        f'Venta registrada: {producto_tienda.nombre} '
                        f'({cantidad} unidad{"es" if cantidad != 1 else ""}). '
                        f'Total: ${total:,.0f}. '
                        f'Inventario restante: {producto_tienda.stock}.'
                    ),
                )
                return redirect('tienda:panel')
    return _render_formulario(
        request, form, 'Registrar venta', 'fa-cart-shopping',
        'Registrar venta', 'btn-success',
    )


@staff_member_required
def registrar_compra(request):
    form = CompraTiendaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            producto_tienda = ProductoTienda.objects.select_for_update().get(
                id=form.cleaned_data['producto'].id,
                activo=True,
            )
            cantidad = form.cleaned_data['cantidad']
            costo_unitario = form.cleaned_data['costo_unitario']
            total = costo_unitario * cantidad
            MovimientoTienda.objects.create(
                cuenta=form.cleaned_data['cuenta'],
                tipo=MovimientoTienda.Tipos.EGRESO,
                origen=MovimientoTienda.Origenes.COMPRA,
                concepto=f'Compra - {producto_tienda.nombre}',
                valor=total,
                producto=producto_tienda,
                cantidad=cantidad,
                observaciones=form.cleaned_data['observaciones'],
                registrado_por=request.user,
            )
            stock_anterior = producto_tienda.stock
            producto_tienda.stock += cantidad
            campos_actualizados = ['stock', 'actualizado']
            if form.cleaned_data['actualizar_costo']:
                producto_tienda.costo_unitario = costo_unitario
                campos_actualizados.append('costo_unitario')
            producto_tienda.save(update_fields=campos_actualizados)
            AjusteInventario.objects.create(
                producto=producto_tienda,
                tipo=AjusteInventario.Tipos.ENTRADA,
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_nuevo=producto_tienda.stock,
                motivo='Entrada automática por compra.',
                registrado_por=request.user,
            )
        messages.success(request, f'Compra registrada por ${total:,.0f}.')
        return redirect('tienda:panel')
    return _render_formulario(
        request, form, 'Registrar compra de productos', 'fa-boxes-stacked',
        'Registrar compra', 'btn-warning',
    )


@staff_member_required
def registrar_gasto(request):
    form = GastoTiendaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        MovimientoTienda.objects.create(
            cuenta=form.cleaned_data['cuenta'],
            tipo=MovimientoTienda.Tipos.EGRESO,
            origen=MovimientoTienda.Origenes.GASTO,
            concepto=form.cleaned_data['concepto'],
            valor=form.cleaned_data['valor'],
            fecha=form.cleaned_data['fecha'],
            observaciones=form.cleaned_data['observaciones'],
            registrado_por=request.user,
        )
        messages.success(request, 'Gasto de tienda registrado correctamente.')
        return redirect('tienda:panel')
    return _render_formulario(
        request, form, 'Registrar gasto de tienda', 'fa-arrow-trend-down',
        'Registrar gasto', 'btn-danger',
    )


@staff_member_required
def ajustar_inventario(request):
    form = AjusteInventarioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            producto_tienda = ProductoTienda.objects.select_for_update().get(
                id=form.cleaned_data['producto'].id,
                activo=True,
            )
            cantidad = form.cleaned_data['cantidad']
            tipo = form.cleaned_data['tipo']
            stock_anterior = producto_tienda.stock
            if tipo == AjusteInventario.Tipos.SALIDA and cantidad > stock_anterior:
                form.add_error(
                    'cantidad',
                    f'No hay inventario suficiente. Disponibles: {stock_anterior}.',
                )
            else:
                if tipo == AjusteInventario.Tipos.ENTRADA:
                    producto_tienda.stock += cantidad
                else:
                    producto_tienda.stock -= cantidad
                producto_tienda.save(update_fields=['stock', 'actualizado'])
                AjusteInventario.objects.create(
                    producto=producto_tienda,
                    tipo=tipo,
                    cantidad=cantidad,
                    stock_anterior=stock_anterior,
                    stock_nuevo=producto_tienda.stock,
                    motivo=form.cleaned_data['motivo'],
                    registrado_por=request.user,
                )
                messages.success(request, 'Inventario ajustado correctamente.')
                return redirect('tienda:panel')
    return _render_formulario(
        request, form, 'Ajustar inventario', 'fa-box-open',
        'Guardar ajuste', 'btn-info',
    )
