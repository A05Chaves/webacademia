import calendar
from datetime import date
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AbonoVentaForm,
    AjusteInventarioForm,
    CategoriaProductoForm,
    ClienteTiendaForm,
    CompraTiendaForm,
    CuentaTiendaForm,
    GastoTiendaForm,
    ProductoTiendaForm,
    SubcategoriaProductoForm,
    VentaTiendaForm,
)
from .models import (
    AjusteInventario,
    AplicacionAbonoCuota,
    CategoriaProducto,
    ClienteTienda,
    CuentaTienda,
    CuotaVentaTienda,
    DetalleVentaTienda,
    Monedas,
    MovimientoTienda,
    ProductoTienda,
    SubcategoriaProducto,
    VentaTienda,
)


MARCA_TIENDA = 'Bross Fight Sports'


def _render_formulario(request, form, titulo, icono, texto_boton, clase_boton='btn-success', volver_url='tienda:panel'):
    return render(request, 'tienda/formulario.html', {
        'form': form, 'titulo': titulo, 'icono': icono,
        'texto_boton': texto_boton, 'clase_boton': clase_boton,
        'volver_url': volver_url,
    })


def _rango_fechas(request):
    hoy = timezone.localdate()
    try:
        desde = timezone.datetime.strptime(request.GET.get('desde', ''), '%Y-%m-%d').date()
    except ValueError:
        desde = hoy.replace(day=1)
    try:
        hasta = timezone.datetime.strptime(request.GET.get('hasta', ''), '%Y-%m-%d').date()
    except ValueError:
        hasta = hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def _sumar_meses(fecha, meses):
    indice = fecha.year * 12 + fecha.month - 1 + meses
    anio, mes_cero = divmod(indice, 12)
    mes = mes_cero + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def _crear_cuotas(venta):
    if venta.modalidad != VentaTienda.Modalidades.CREDITO:
        return
    numero_cuotas = max(venta.numero_cuotas, 1)
    valor_base = (venta.total / numero_cuotas).quantize(Decimal('0.01'))
    acumulado = Decimal('0')
    for numero in range(1, numero_cuotas + 1):
        valor = valor_base if numero < numero_cuotas else venta.total - acumulado
        acumulado += valor
        CuotaVentaTienda.objects.create(
            venta=venta,
            numero=numero,
            fecha_vencimiento=_sumar_meses(venta.fecha_vencimiento, numero - 1),
            valor=valor,
            saldo=valor,
        )


def _resumen_moneda(moneda, desde, hasta):
    cuentas = list(CuentaTienda.objects.filter(moneda=moneda))
    saldo = sum((cuenta.saldo_actual for cuenta in cuentas if cuenta.activa), Decimal('0'))
    movimientos = MovimientoTienda.objects.filter(
        moneda=moneda, fecha__date__range=(desde, hasta)
    )
    entradas = movimientos.filter(tipo=MovimientoTienda.Tipos.INGRESO).aggregate(
        total=Sum('valor')
    )['total'] or Decimal('0')
    salidas = movimientos.filter(tipo=MovimientoTienda.Tipos.EGRESO).aggregate(
        total=Sum('valor')
    )['total'] or Decimal('0')
    ventas = VentaTienda.objects.filter(
        moneda=moneda, fecha__date__range=(desde, hasta)
    ).exclude(estado=VentaTienda.Estados.ANULADA).aggregate(total=Sum('total'))['total'] or Decimal('0')
    ventas_anteriores = movimientos.filter(
        origen=MovimientoTienda.Origenes.VENTA, venta__isnull=True
    ).aggregate(total=Sum('valor'))['total'] or Decimal('0')
    ventas += ventas_anteriores
    cartera = VentaTienda.objects.filter(moneda=moneda).exclude(
        estado__in=[VentaTienda.Estados.PAGADA, VentaTienda.Estados.ANULADA]
    ).aggregate(total=Sum('saldo_pendiente'))['total'] or Decimal('0')
    inventario = sum(
        (p.valor_inventario for p in ProductoTienda.objects.filter(moneda=moneda, activo=True)),
        Decimal('0'),
    )
    return {
        'codigo': moneda,
        'nombre': dict(Monedas.choices)[moneda],
        'simbolo': '$' if moneda == Monedas.COP else 'US$',
        'saldo': saldo,
        'entradas': entradas,
        'salidas': salidas,
        'flujo_neto': entradas - salidas,
        'ventas': ventas,
        'cartera': cartera,
        'inventario': inventario,
    }


@staff_member_required
def panel(request):
    desde, hasta = _rango_fechas(request)
    resumenes = [_resumen_moneda(moneda, desde, hasta) for moneda in (Monedas.COP, Monedas.USD)]
    productos_bajo_stock_qs = ProductoTienda.objects.filter(
        activo=True, stock_minimo__gt=0, stock__lte=models_f_stock_minimo()
    ).select_related('categoria', 'subcategoria')
    cantidad_productos_bajo_stock = productos_bajo_stock_qs.count()
    productos_bajo_stock = productos_bajo_stock_qs.order_by('stock', 'nombre')[:3]
    ultima_venta = VentaTienda.objects.exclude(
        estado=VentaTienda.Estados.ANULADA
    ).select_related('cliente').prefetch_related('detalles').first()
    movimientos = MovimientoTienda.objects.filter(
        fecha__date__range=(desde, hasta)
    ).select_related('cuenta', 'producto', 'venta')[:15]
    creditos = VentaTienda.objects.exclude(
        estado__in=[VentaTienda.Estados.PAGADA, VentaTienda.Estados.ANULADA]
    ).select_related('cliente')[:8]

    nombres_meses = ('Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic')
    hoy = timezone.localdate()
    labels, series = [], {Monedas.COP: [], Monedas.USD: []}
    egresos_cop = []
    actual = hoy.year * 12 + hoy.month - 1
    for desplazamiento in range(5, -1, -1):
        anio, indice = divmod(actual - desplazamiento, 12)
        mes = indice + 1
        labels.append(f'{nombres_meses[indice]} {anio}')
        for moneda in series:
            total = MovimientoTienda.objects.filter(
                moneda=moneda, tipo=MovimientoTienda.Tipos.INGRESO,
                fecha__year=anio, fecha__month=mes,
            ).aggregate(total=Sum('valor'))['total'] or 0
            series[moneda].append(float(total))
        egreso_cop = MovimientoTienda.objects.filter(
            moneda=Monedas.COP, tipo=MovimientoTienda.Tipos.EGRESO,
            fecha__year=anio, fecha__month=mes,
        ).aggregate(total=Sum('valor'))['total'] or 0
        egresos_cop.append(float(egreso_cop))

    ventas_por_producto = MovimientoTienda.objects.filter(
        origen=MovimientoTienda.Origenes.VENTA, producto__isnull=False
    ).values('producto__nombre').annotate(total=Sum('valor')).order_by('-total')[:6]
    labels_productos = [fila['producto__nombre'] for fila in ventas_por_producto]
    ventas_productos = [float(fila['total']) for fila in ventas_por_producto]

    cop = resumenes[0]
    return render(request, 'tienda/panel.html', {
        'resumenes': resumenes,
        'desde': desde, 'hasta': hasta,
        'productos_bajo_stock': productos_bajo_stock,
        'cantidad_productos_bajo_stock': cantidad_productos_bajo_stock,
        'ultima_venta': ultima_venta,
        'movimientos': movimientos, 'creditos': creditos,
        'labels_flujo': labels,
        'entradas_cop': series[Monedas.COP],
        'entradas_usd': series[Monedas.USD],
        # Alias conservados para integraciones y reportes existentes.
        'saldo_total': cop['saldo'], 'ventas_mes': cop['ventas'],
        'egresos_mes': cop['salidas'], 'egresos_acumulados': MovimientoTienda.objects.filter(
            moneda=Monedas.COP, tipo=MovimientoTienda.Tipos.EGRESO
        ).aggregate(total=Sum('valor'))['total'] or 0,
        'utilidad_mes': cop['ventas'] - cop['salidas'],
        'valor_inventario': cop['inventario'],
        'ventas_flujo': series[Monedas.COP],
        'egresos_flujo': egresos_cop, 'labels_productos': labels_productos,
        'ventas_productos': ventas_productos,
    })


def models_f_stock_minimo():
    from django.db.models import F
    return F('stock_minimo')


@staff_member_required
def configuracion(request):
    cuentas = list(CuentaTienda.objects.all())
    for item in cuentas:
        item.saldo_calculado = item.saldo_actual
    return render(request, 'tienda/configuracion.html', {
        'cuentas': cuentas,
        'productos': ProductoTienda.objects.select_related('categoria', 'subcategoria'),
        'categorias': CategoriaProducto.objects.prefetch_related('subcategorias'),
        'clientes': ClienteTienda.objects.all()[:30],
    })


@staff_member_required
def cuenta(request, cuenta_id=None):
    instancia = get_object_or_404(CuentaTienda, id=cuenta_id) if cuenta_id else None
    form = CuentaTiendaForm(request.POST or None, instance=instancia)
    if request.method == 'POST' and form.is_valid():
        guardada = form.save()
        messages.success(request, f'Cuenta "{guardada.nombre}" guardada correctamente.')
        return redirect('tienda:configuracion')
    return _render_formulario(
        request, form, 'Editar cuenta' if instancia else 'Nueva cuenta',
        'fa-building-columns', 'Guardar cuenta', volver_url='tienda:configuracion'
    )


@staff_member_required
@require_POST
def cambiar_estado_cuenta(request, cuenta_id):
    cuenta_tienda = get_object_or_404(CuentaTienda, id=cuenta_id)
    cuenta_tienda.activa = not cuenta_tienda.activa
    cuenta_tienda.save(update_fields=['activa', 'fecha_inactivacion'])
    messages.success(request, f'Cuenta {"reactivada" if cuenta_tienda.activa else "inhabilitada"}.')
    return redirect('tienda:configuracion')


@staff_member_required
def categoria(request, categoria_id=None):
    instancia = get_object_or_404(CategoriaProducto, id=categoria_id) if categoria_id else None
    form = CategoriaProductoForm(request.POST or None, instance=instancia)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Categoría guardada correctamente.')
        return redirect('tienda:configuracion')
    return _render_formulario(request, form, 'Categoría de productos', 'fa-tags', 'Guardar', volver_url='tienda:configuracion')


@staff_member_required
def subcategoria(request, subcategoria_id=None):
    instancia = get_object_or_404(SubcategoriaProducto, id=subcategoria_id) if subcategoria_id else None
    form = SubcategoriaProductoForm(request.POST or None, instance=instancia)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Subcategoría guardada correctamente.')
        return redirect('tienda:configuracion')
    return _render_formulario(request, form, 'Subcategoría de productos', 'fa-tag', 'Guardar', volver_url='tienda:configuracion')


@staff_member_required
def cliente(request, cliente_id=None):
    instancia = get_object_or_404(ClienteTienda, id=cliente_id) if cliente_id else None
    form = ClienteTiendaForm(request.POST or None, instance=instancia)
    if request.method == 'POST' and form.is_valid():
        cliente_guardado = form.save()
        messages.success(request, f'Cliente "{cliente_guardado.nombres}" guardado.')
        destino = request.GET.get('next')
        return redirect(destino if destino and destino.startswith('/') else 'tienda:configuracion')
    return _render_formulario(request, form, 'Datos del comprador', 'fa-user', 'Guardar cliente', volver_url='tienda:configuracion')


@staff_member_required
def producto(request, producto_id=None):
    instancia = get_object_or_404(ProductoTienda, id=producto_id) if producto_id else None
    form = ProductoTiendaForm(request.POST or None, instance=instancia)
    if request.method == 'POST' and form.is_valid():
        creando = instancia is None
        guardado = form.save(commit=False)
        if creando:
            guardado.stock = form.cleaned_data.get('stock_inicial') or 0
        guardado.save()
        if creando and guardado.stock:
            AjusteInventario.objects.create(
                producto=guardado, tipo=AjusteInventario.Tipos.ENTRADA,
                cantidad=guardado.stock, stock_anterior=0, stock_nuevo=guardado.stock,
                costo_unitario=guardado.costo_unitario,
                motivo='Inventario inicial del producto.', registrado_por=request.user,
            )
        messages.success(request, f'Producto "{guardado.nombre_variante}" guardado.')
        return redirect('tienda:configuracion')
    return _render_formulario(
        request, form, 'Editar producto' if instancia else 'Nuevo producto',
        'fa-shirt', 'Guardar producto', volver_url='tienda:configuracion'
    )


@staff_member_required
@require_POST
def cambiar_estado_producto(request, producto_id):
    item = get_object_or_404(ProductoTienda, id=producto_id)
    item.activo = not item.activo
    if not item.activo:
        item.motivo_inactivacion = request.POST.get('motivo', 'Producto obsoleto')
    item.save()
    messages.success(request, f'Producto {"reactivado" if item.activo else "marcado como obsoleto"}.')
    return redirect('tienda:configuracion')


@staff_member_required
def registrar_venta(request):
    form = VentaTiendaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        venta = None
        item = None
        cantidad = None
        total = None
        with transaction.atomic():
            item = ProductoTienda.objects.select_for_update().get(id=form.cleaned_data['producto'].id, activo=True)
            cantidad = form.cleaned_data['cantidad']
            if cantidad > item.stock:
                form.add_error('cantidad', f'No hay inventario suficiente. Disponibles: {item.stock}.')
            else:
                subtotal = item.precio_venta * cantidad
                porcentaje = form.cleaned_data.get('descuento_porcentaje') or Decimal('0')
                descuento = (subtotal * porcentaje / Decimal('100')).quantize(Decimal('0.01'))
                total = subtotal - descuento
                modalidad = form.cleaned_data['modalidad']
                cliente_venta = form.cleaned_data.get('cliente')
                if form.cleaned_data.get('registrar_comprador'):
                    cliente_venta = ClienteTienda.objects.create(
                        nombres=form.cleaned_data['comprador_nombres'],
                        tipo_documento=form.cleaned_data['comprador_tipo_documento'],
                        numero_documento=form.cleaned_data['comprador_numero_documento'],
                        telefono_whatsapp=form.cleaned_data.get('comprador_whatsapp', ''),
                        correo=form.cleaned_data.get('comprador_correo', ''),
                        acepta_whatsapp=form.cleaned_data.get('comprador_acepta_whatsapp', False),
                    )
                venta = VentaTienda.objects.create(
                    cliente=cliente_venta, modalidad=modalidad,
                    estado=VentaTienda.Estados.PAGADA if modalidad == VentaTienda.Modalidades.CONTADO else VentaTienda.Estados.PENDIENTE,
                    moneda=item.moneda, subtotal=subtotal, descuento=descuento, total=total,
                    saldo_pendiente=total if modalidad == VentaTienda.Modalidades.CREDITO else 0,
                    fecha_vencimiento=form.cleaned_data.get('fecha_vencimiento'),
                    numero_cuotas=form.cleaned_data.get('numero_cuotas') or 1,
                    observaciones=form.cleaned_data['observaciones'], registrado_por=request.user,
                )
                DetalleVentaTienda.objects.create(
                    venta=venta, producto=item, descripcion=item.nombre_variante,
                    cantidad=cantidad, precio_unitario=item.precio_venta,
                    costo_unitario=item.costo_unitario, descuento=descuento, total=total,
                )
                _crear_cuotas(venta)
                if modalidad == VentaTienda.Modalidades.CONTADO:
                    MovimientoTienda.objects.create(
                        cuenta=form.cleaned_data['cuenta'], tipo=MovimientoTienda.Tipos.INGRESO,
                        origen=MovimientoTienda.Origenes.VENTA, concepto=f'Venta {venta.numero}',
                        valor=total, moneda=item.moneda, producto=item, venta=venta,
                        cantidad=cantidad, costo_unitario=item.costo_unitario,
                        observaciones=form.cleaned_data['observaciones'], registrado_por=request.user,
                    )
                item.stock -= cantidad
                item.save(update_fields=['stock', 'actualizado'])
        if venta:
            messages.success(
                request,
                f'Venta registrada: {item.nombre_variante} ({cantidad} unidad{"es" if cantidad != 1 else ""}). '
                f'Total: {total:,.2f} {item.moneda}. Inventario restante: {item.stock}. '
                f'Comprobante: {venta.numero}.',
            )
            if venta.cliente and venta.cliente.correo:
                try:
                    _enviar_comprobante_correo(venta)
                except Exception:
                    messages.warning(
                        request,
                        f'La venta quedó registrada, pero no fue posible enviar el correo a {venta.cliente.correo}. '
                        'Puede reintentarlo desde el comprobante.',
                    )
                else:
                    messages.success(
                        request, f'Comprobante enviado a {venta.cliente.correo}.'
                    )
            if 'modalidad' not in request.POST:
                return redirect('tienda:panel')
            return redirect('tienda:detalle_venta', venta_id=venta.id)
    return render(request, 'tienda/venta_formulario.html', {'form': form})


@staff_member_required
def registrar_compra(request):
    form = CompraTiendaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            item = ProductoTienda.objects.select_for_update().get(id=form.cleaned_data['producto'].id, activo=True)
            cantidad, costo_nuevo = form.cleaned_data['cantidad'], form.cleaned_data['costo_unitario']
            total = costo_nuevo * cantidad
            cuenta_tienda = form.cleaned_data['cuenta']
            MovimientoTienda.objects.create(
                cuenta=cuenta_tienda, tipo=MovimientoTienda.Tipos.EGRESO,
                origen=MovimientoTienda.Origenes.COMPRA, concepto=f'Compra - {item.nombre_variante}',
                valor=total, moneda=cuenta_tienda.moneda, producto=item, cantidad=cantidad,
                costo_unitario=costo_nuevo, observaciones=form.cleaned_data['observaciones'],
                registrado_por=request.user,
            )
            stock_anterior = item.stock
            unidades_totales = stock_anterior + cantidad
            item.costo_unitario = (
                (item.costo_unitario * stock_anterior + costo_nuevo * cantidad) / unidades_totales
            ).quantize(Decimal('0.01'))
            item.stock = unidades_totales
            item.save(update_fields=['stock', 'costo_unitario', 'actualizado'])
            AjusteInventario.objects.create(
                producto=item, tipo=AjusteInventario.Tipos.ENTRADA, cantidad=cantidad,
                stock_anterior=stock_anterior, stock_nuevo=item.stock, costo_unitario=costo_nuevo,
                motivo='Entrada automática por compra.', registrado_por=request.user,
            )
        messages.success(request, f'Compra registrada. Nuevo costo promedio: {item.costo_unitario:,.2f} {item.moneda}.')
        return redirect('tienda:panel')
    return _render_formulario(request, form, 'Registrar compra', 'fa-boxes-stacked', 'Registrar compra', 'btn-warning')


@staff_member_required
def registrar_gasto(request):
    form = GastoTiendaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cuenta_tienda = form.cleaned_data['cuenta']
        MovimientoTienda.objects.create(
            cuenta=cuenta_tienda, tipo=MovimientoTienda.Tipos.EGRESO,
            origen=MovimientoTienda.Origenes.GASTO, concepto=form.cleaned_data['concepto'],
            valor=form.cleaned_data['valor'], moneda=cuenta_tienda.moneda,
            fecha=form.cleaned_data['fecha'], observaciones=form.cleaned_data['observaciones'],
            registrado_por=request.user,
        )
        messages.success(request, 'Gasto de tienda registrado.')
        return redirect('tienda:panel')
    return _render_formulario(request, form, 'Registrar gasto', 'fa-arrow-trend-down', 'Registrar gasto', 'btn-danger')


@staff_member_required
def ajustar_inventario(request):
    form = AjusteInventarioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            item = ProductoTienda.objects.select_for_update().get(id=form.cleaned_data['producto'].id, activo=True)
            cantidad, tipo = form.cleaned_data['cantidad'], form.cleaned_data['tipo']
            anterior = item.stock
            if tipo == AjusteInventario.Tipos.SALIDA and cantidad > anterior:
                form.add_error('cantidad', f'No hay inventario suficiente. Disponibles: {anterior}.')
            else:
                item.stock = anterior + cantidad if tipo == AjusteInventario.Tipos.ENTRADA else anterior - cantidad
                item.save(update_fields=['stock', 'actualizado'])
                AjusteInventario.objects.create(
                    producto=item, tipo=tipo, cantidad=cantidad, stock_anterior=anterior,
                    stock_nuevo=item.stock, costo_unitario=item.costo_unitario,
                    motivo=form.cleaned_data['motivo'], registrado_por=request.user,
                )
                messages.success(request, 'Inventario ajustado correctamente.')
                return redirect('tienda:panel')
    return _render_formulario(request, form, 'Ajustar inventario', 'fa-box-open', 'Guardar ajuste', 'btn-info')


@staff_member_required
def creditos(request):
    estado = request.GET.get('estado', 'pendientes')
    ventas = VentaTienda.objects.filter(modalidad=VentaTienda.Modalidades.CREDITO).select_related('cliente')
    if estado == 'pendientes':
        ventas = ventas.exclude(estado__in=[VentaTienda.Estados.PAGADA, VentaTienda.Estados.ANULADA])
    elif estado == 'pagadas':
        ventas = ventas.filter(estado=VentaTienda.Estados.PAGADA)
    return render(request, 'tienda/creditos.html', {'ventas': ventas, 'estado_filtro': estado})


@staff_member_required
def registrar_abono(request, venta_id):
    venta = get_object_or_404(VentaTienda, id=venta_id, modalidad=VentaTienda.Modalidades.CREDITO)
    cuota_inicial = request.GET.get('cuota') if request.method == 'GET' else None
    valores_iniciales = {'cuota': cuota_inicial} if cuota_inicial else None
    form = AbonoVentaForm(request.POST or None, venta=venta, initial=valores_iniciales)
    if request.method == 'POST' and form.is_valid():
        cuenta_tienda = form.cleaned_data['cuenta']
        with transaction.atomic():
            venta = VentaTienda.objects.select_for_update().get(id=venta.id)
            movimiento = MovimientoTienda.objects.create(
                cuenta=cuenta_tienda, tipo=MovimientoTienda.Tipos.INGRESO,
                origen=MovimientoTienda.Origenes.ABONO, concepto=f'Abono {venta.numero}',
                valor=form.cleaned_data['valor'], moneda=venta.moneda, venta=venta,
                observaciones=form.cleaned_data['observaciones'], registrado_por=request.user,
            )
            restante = form.cleaned_data['valor']
            cuota_elegida = form.cleaned_data.get('cuota')
            cuotas_pendientes = list(
                venta.cuotas.select_for_update().filter(saldo__gt=0).order_by(
                    'fecha_vencimiento', 'numero'
                )
            )
            if cuota_elegida:
                cuotas_pendientes.sort(
                    key=lambda cuota: (
                        0 if cuota.id == cuota_elegida.id else 1,
                        cuota.fecha_vencimiento,
                        cuota.numero,
                    )
                )
            for cuota in cuotas_pendientes:
                if restante <= 0:
                    break
                aplicado = min(restante, cuota.saldo)
                cuota.saldo -= aplicado
                cuota.estado = (
                    CuotaVentaTienda.Estados.PAGADA if cuota.saldo == 0
                    else CuotaVentaTienda.Estados.PARCIAL
                )
                cuota.save(update_fields=['saldo', 'estado'])
                AplicacionAbonoCuota.objects.create(
                    movimiento=movimiento, cuota=cuota, valor=aplicado
                )
                restante -= aplicado
            venta.actualizar_saldo()
        messages.success(request, 'Abono registrado. La cartera fue actualizada.')
        return redirect('tienda:detalle_venta', venta_id=venta.id)
    return _render_formulario(request, form, f'Abono a {venta.numero}', 'fa-hand-holding-dollar', 'Registrar abono', volver_url='tienda:creditos')


@staff_member_required
def detalle_venta(request, venta_id):
    venta = get_object_or_404(
        VentaTienda.objects.select_related('cliente').prefetch_related(
            'detalles__producto', 'movimientos__cuenta', 'cuotas__aplicaciones'
        ),
        id=venta_id,
    )
    texto = f'Comprobante {venta.numero}\nTotal: {venta.total:,.2f} {venta.moneda}\nSaldo: {venta.saldo_pendiente:,.2f} {venta.moneda}'
    telefono = ''.join(filter(str.isdigit, venta.cliente.telefono_whatsapp)) if venta.cliente else ''
    whatsapp_url = f'https://wa.me/{telefono}?text={quote(texto)}' if telefono else ''
    return render(request, 'tienda/detalle_venta.html', {
        'venta': venta, 'whatsapp_url': whatsapp_url,
        'puede_whatsapp': bool(telefono and venta.cliente.acepta_whatsapp),
    })


def _pdf_comprobante(venta):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=letter, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f'Comprobante {venta.numero}', author=MARCA_TIENDA,
    )
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(
        name='TituloTienda', parent=estilos['Title'], fontName='Helvetica-Bold',
        fontSize=18, textColor=colors.HexColor('#17365D'), spaceAfter=4,
    ))
    estilos.add(ParagraphStyle(
        name='Derecha', parent=estilos['Normal'], alignment=TA_RIGHT,
    ))
    estilos.add(ParagraphStyle(
        name='Pie', parent=estilos['Normal'], alignment=TA_CENTER,
        fontSize=8, textColor=colors.HexColor('#666666'),
    ))
    logo = Image(
        str(settings.BASE_DIR / 'static' / 'img' / 'bross-fight-sport-logo.png'),
        width=72 * mm,
        height=17.84 * mm,
    )
    logo.hAlign = 'CENTER'
    historia = [
        logo,
        Spacer(1, 2 * mm),
        Paragraph(MARCA_TIENDA, estilos['TituloTienda']),
        Paragraph('Comprobante interno de venta', estilos['Normal']),
        Spacer(1, 8 * mm),
    ]
    cabecera = Table([
        [Paragraph(f'<b>Comprobante:</b> {venta.numero}', estilos['Normal']),
         Paragraph(f'<b>Fecha:</b> {timezone.localtime(venta.fecha):%d/%m/%Y %H:%M}', estilos['Derecha'])],
        [Paragraph(f'<b>Modalidad:</b> {venta.get_modalidad_display()}', estilos['Normal']),
         Paragraph(f'<b>Estado:</b> {venta.get_estado_display()}', estilos['Derecha'])],
    ], colWidths=[85 * mm, 85 * mm])
    cabecera.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#AAB7C4')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#D7DEE5')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F6F8')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    historia.extend([cabecera, Spacer(1, 6 * mm)])
    if venta.cliente:
        historia.append(Paragraph(
            f'<b>Comprador:</b> {venta.cliente.nombres}<br/>'
            f'<b>Documento:</b> {venta.cliente.get_tipo_documento_display()} {venta.cliente.numero_documento}<br/>'
            f'<b>Contacto:</b> {venta.cliente.telefono_whatsapp or "No registrado"}',
            estilos['Normal'],
        ))
    else:
        historia.append(Paragraph('<b>Comprador:</b> Consumidor final', estilos['Normal']))
    historia.append(Spacer(1, 6 * mm))
    filas = [['Producto', 'Cant.', 'Precio', 'Descuento', 'Total']]
    for detalle in venta.detalles.all():
        filas.append([
            detalle.descripcion, str(detalle.cantidad),
            f'{detalle.precio_unitario:,.2f}', f'{detalle.descuento:,.2f}',
            f'{detalle.total:,.2f}',
        ])
    tabla = Table(filas, colWidths=[78 * mm, 16 * mm, 28 * mm, 25 * mm, 28 * mm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17365D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#BCC7D1')),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7F9FA')]),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    historia.extend([tabla, Spacer(1, 5 * mm)])
    totales = Table([
        ['Subtotal', f'{venta.subtotal:,.2f} {venta.moneda}'],
        ['Descuento', f'{venta.descuento:,.2f} {venta.moneda}'],
        ['TOTAL', f'{venta.total:,.2f} {venta.moneda}'],
        ['Saldo pendiente', f'{venta.saldo_pendiente:,.2f} {venta.moneda}'],
    ], colWidths=[45 * mm, 45 * mm], hAlign='RIGHT')
    totales.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('LINEABOVE', (0, 2), (-1, 2), 0.8, colors.HexColor('#17365D')),
        ('TEXTCOLOR', (0, 3), (-1, 3), colors.HexColor('#B02A37')),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    historia.extend([totales, Spacer(1, 9 * mm)])
    historia.append(Paragraph(
        'Este comprobante es un soporte interno y no reemplaza la factura electrónica cuando legalmente sea exigible.',
        estilos['Pie'],
    ))
    documento.build(historia)
    return buffer.getvalue()


def _enviar_comprobante_correo(venta):
    if not venta.cliente or not venta.cliente.correo:
        raise ValueError('La venta no tiene un correo de comprador asociado.')
    destinatario = venta.cliente.correo
    asunto = f'Comprobante de compra {venta.numero} - {MARCA_TIENDA}'
    cuerpo = (
        f'Hola {venta.cliente.nombres},\n\n'
        f'Adjuntamos el comprobante de su compra {venta.numero} por '
        f'{venta.total:,.2f} {venta.moneda}.\n'
    )
    if venta.saldo_pendiente:
        cuerpo += f'Saldo pendiente: {venta.saldo_pendiente:,.2f} {venta.moneda}.\n'
    cuerpo += f'\nGracias por su compra.\n{MARCA_TIENDA}'
    mensaje = EmailMessage(
        subject=asunto,
        body=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario],
    )
    mensaje.attach(
        f'comprobante-{venta.numero}.pdf',
        _pdf_comprobante(venta),
        'application/pdf',
    )
    try:
        mensaje.send(fail_silently=False)
    except Exception as error:
        VentaTienda.objects.filter(pk=venta.pk).update(
            error_envio_correo=str(error)[:1500],
        )
        venta.error_envio_correo = str(error)[:1500]
        raise
    fecha_envio = timezone.now()
    VentaTienda.objects.filter(pk=venta.pk).update(
        email_enviado_a=destinatario,
        fecha_envio_correo=fecha_envio,
        error_envio_correo='',
    )
    venta.email_enviado_a = destinatario
    venta.fecha_envio_correo = fecha_envio
    venta.error_envio_correo = ''


@staff_member_required
@require_POST
def enviar_comprobante_correo(request, venta_id):
    venta = get_object_or_404(
        VentaTienda.objects.select_related('cliente').prefetch_related('detalles'), id=venta_id
    )
    if not venta.cliente or not venta.cliente.correo:
        messages.error(request, 'Esta venta no tiene un correo de comprador asociado.')
    else:
        try:
            _enviar_comprobante_correo(venta)
        except Exception:
            messages.error(request, 'No fue posible enviar el correo. Revise la configuración SMTP e inténtelo nuevamente.')
        else:
            messages.success(request, f'Comprobante enviado a {venta.cliente.correo}.')
    return redirect('tienda:detalle_venta', venta_id=venta.id)


@staff_member_required
def descargar_comprobante(request, venta_id):
    venta = get_object_or_404(
        VentaTienda.objects.select_related('cliente').prefetch_related('detalles'), id=venta_id
    )
    respuesta = HttpResponse(_pdf_comprobante(venta), content_type='application/pdf')
    respuesta['Content-Disposition'] = f'attachment; filename="comprobante-{venta.numero}.pdf"'
    return respuesta


@staff_member_required
def paz_y_salvo(request, venta_id):
    venta = get_object_or_404(VentaTienda.objects.select_related('cliente'), id=venta_id)
    if venta.estado != VentaTienda.Estados.PAGADA or not venta.cliente:
        messages.error(request, 'El paz y salvo solo se genera para una venta pagada con comprador identificado.')
        return redirect('tienda:detalle_venta', venta_id=venta.id)
    return render(request, 'tienda/paz_y_salvo.html', {'venta': venta})


@staff_member_required
def consultas(request):
    desde, hasta = _rango_fechas(request)
    moneda = request.GET.get('moneda', '')
    producto_id = request.GET.get('producto', '')
    movimientos = MovimientoTienda.objects.filter(fecha__date__range=(desde, hasta)).select_related('cuenta', 'producto', 'venta')
    ajustes = AjusteInventario.objects.filter(fecha__date__range=(desde, hasta)).select_related('producto')
    if moneda in Monedas.values:
        movimientos = movimientos.filter(moneda=moneda)
        ajustes = ajustes.filter(producto__moneda=moneda)
    if producto_id.isdigit():
        movimientos = movimientos.filter(producto_id=producto_id)
        ajustes = ajustes.filter(producto_id=producto_id)
    return render(request, 'tienda/consultas.html', {
        'desde': desde, 'hasta': hasta, 'moneda_filtro': moneda,
        'producto_filtro': producto_id, 'monedas': Monedas.choices,
        'productos': ProductoTienda.objects.all(), 'movimientos': movimientos[:200],
        'ajustes': ajustes[:200], 'cuentas': CuentaTienda.objects.all(),
    })
