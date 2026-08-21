from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from alumnos.models import Alumno
from finanzas.models import MovimientoFinanciero

from .forms import ProductoTiendaForm, VentaTiendaForm
from .models import (
    AjusteInventario, AplicacionAbonoCuota, CategoriaMovimientoTienda,
    CategoriaProducto, ClienteTienda, DisciplinaProducto,
    CuentaTienda, CuotaVentaTienda, DetalleVentaTienda, MovimientoTienda,
    LineaModeloProducto, MarcaProducto, ProductoTienda, VentaTienda,
)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TiendaTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin_tienda',
            password='clave-segura-pruebas',
            is_staff=True,
        )
        self.client.force_login(self.admin)
        self.cuenta = CuentaTienda.objects.create(
            nombre='Caja tienda',
            tipo=CuentaTienda.Tipos.EFECTIVO,
            saldo_inicial=200000,
        )
        self.producto = ProductoTienda.objects.create(
            nombre='Camiseta academia',
            referencia='CAM-001',
            precio_venta=80000,
            costo_unitario=40000,
            stock=10,
            stock_minimo=2,
        )

    def test_configura_catalogos_y_los_asigna_al_producto(self):
        response = self.client.post(reverse('tienda:crear_marca'), {
            'nombre': 'Tatami', 'activa': 'on',
        })
        self.assertRedirects(response, reverse('tienda:configuracion'))
        marca = MarcaProducto.objects.get(nombre='Tatami')

        response = self.client.post(reverse('tienda:crear_linea_modelo'), {
            'marca': marca.id, 'nombre': 'Nova Absolute', 'activa': 'on',
        })
        self.assertRedirects(response, reverse('tienda:configuracion'))
        linea = LineaModeloProducto.objects.get(nombre='Nova Absolute')

        response = self.client.post(reverse('tienda:crear_disciplina_producto'), {
            'nombre': 'Jiu Jitsu', 'activa': 'on',
        })
        self.assertRedirects(response, reverse('tienda:configuracion'))
        disciplina = DisciplinaProducto.objects.get(nombre='Jiu Jitsu')

        response = self.client.post(reverse('tienda:crear_producto'), {
            'nombre': 'Kimono Nova',
            'marca': marca.id,
            'linea_modelo': linea.id,
            'disciplina': disciplina.id,
            'moneda': 'COP',
            'costo_unitario': '200000',
            'precio_venta': '300000',
            'stock_inicial': '2',
            'stock_minimo': '0',
            'activo': 'on',
        })

        producto = ProductoTienda.objects.get(nombre='Kimono Nova')
        self.assertRedirects(response, reverse('tienda:configuracion'))
        self.assertEqual(producto.marca, marca)
        self.assertEqual(producto.linea_modelo, linea)
        self.assertEqual(producto.disciplina, disciplina)

    def test_lineas_modelos_se_filtran_por_marca(self):
        marca_uno = MarcaProducto.objects.create(nombre='Marca uno')
        marca_dos = MarcaProducto.objects.create(nombre='Marca dos')
        linea_uno = LineaModeloProducto.objects.create(
            marca=marca_uno, nombre='Línea uno',
        )
        LineaModeloProducto.objects.create(marca=marca_dos, nombre='Línea dos')

        response = self.client.get(
            reverse('tienda:lineas_modelos_por_marca'), {'marca': marca_uno.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['resultados'], [
            {'id': linea_uno.id, 'nombre': 'Línea uno'},
        ])

    def test_catalogos_inactivos_no_se_ofrecen_en_productos_nuevos(self):
        marca = MarcaProducto.objects.create(nombre='Marca histórica', activa=False)
        linea = LineaModeloProducto.objects.create(
            marca=marca, nombre='Modelo histórico', activa=False,
        )
        disciplina = DisciplinaProducto.objects.create(
            nombre='Disciplina histórica', activa=False,
        )

        formulario_nuevo = ProductoTiendaForm()
        self.assertNotIn(marca, formulario_nuevo.fields['marca'].queryset)
        self.assertNotIn(linea, formulario_nuevo.fields['linea_modelo'].queryset)
        self.assertNotIn(disciplina, formulario_nuevo.fields['disciplina'].queryset)

        producto = ProductoTienda.objects.create(
            nombre='Producto histórico', marca=marca, linea_modelo=linea,
            disciplina=disciplina, costo_unitario=1, precio_venta=2,
        )
        formulario_edicion = ProductoTiendaForm(instance=producto)
        self.assertIn(marca, formulario_edicion.fields['marca'].queryset)
        self.assertIn(linea, formulario_edicion.fields['linea_modelo'].queryset)
        self.assertIn(disciplina, formulario_edicion.fields['disciplina'].queryset)

    def test_producto_rechaza_linea_modelo_de_otra_marca(self):
        marca_uno = MarcaProducto.objects.create(nombre='Marca A')
        marca_dos = MarcaProducto.objects.create(nombre='Marca B')
        linea = LineaModeloProducto.objects.create(marca=marca_dos, nombre='Modelo B')

        formulario = ProductoTiendaForm(data={
            'nombre': 'Producto inválido',
            'marca': marca_uno.id,
            'linea_modelo': linea.id,
            'moneda': 'COP',
            'costo_unitario': '1',
            'precio_venta': '2',
            'stock_minimo': '0',
            'activo': 'on',
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn('linea_modelo', formulario.errors)

    def test_panel_requiere_usuario_del_personal(self):
        self.client.logout()

        response = self.client.get(reverse('tienda:panel'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_transferencia_mueve_saldo_sin_inflar_resultados_de_tienda(self):
        destino = CuentaTienda.objects.create(
            nombre='Banco tienda',
            tipo=CuentaTienda.Tipos.BANCO,
            saldo_inicial=50000,
            moneda='COP',
        )
        response = self.client.post(reverse('tienda:registrar_transferencia'), {
            'cuenta_origen': self.cuenta.id,
            'cuenta_destino': destino.id,
            'valor': '75000',
            'concepto': 'Consignación diaria',
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'observaciones': 'Traslado interno',
        })

        self.assertRedirects(response, reverse('tienda:panel'))
        movimientos = list(MovimientoTienda.objects.order_by('tipo'))
        self.assertEqual(len(movimientos), 2)
        self.assertTrue(all(
            movimiento.origen == MovimientoTienda.Origenes.TRANSFERENCIA
            for movimiento in movimientos
        ))
        self.assertEqual(movimientos[0].transferencia_id, movimientos[1].transferencia_id)
        self.assertEqual(self.cuenta.saldo_actual, Decimal('125000'))
        self.assertEqual(destino.saldo_actual, Decimal('125000'))

        panel = self.client.get(reverse('tienda:panel'))
        resumen_cop = next(r for r in panel.context['resumenes'] if r['codigo'] == 'COP')
        self.assertEqual(resumen_cop['entradas'], Decimal('0'))
        self.assertEqual(resumen_cop['salidas'], Decimal('0'))

    def test_transferencia_rechaza_cuentas_de_monedas_diferentes(self):
        destino_usd = CuentaTienda.objects.create(
            nombre='Banco dólares',
            tipo=CuentaTienda.Tipos.BANCO,
            saldo_inicial=100,
            moneda='USD',
        )
        response = self.client.post(reverse('tienda:registrar_transferencia'), {
            'cuenta_origen': self.cuenta.id,
            'cuenta_destino': destino_usd.id,
            'valor': '50',
            'concepto': 'Cambio no permitido',
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'misma moneda')
        self.assertFalse(MovimientoTienda.objects.exists())

    def test_transferencia_rechaza_valor_superior_al_saldo(self):
        destino = CuentaTienda.objects.create(
            nombre='Billetera tienda',
            tipo=CuentaTienda.Tipos.BILLETERA,
            moneda='COP',
        )
        response = self.client.post(reverse('tienda:registrar_transferencia'), {
            'cuenta_origen': self.cuenta.id,
            'cuenta_destino': destino.id,
            'valor': '250000',
            'concepto': 'Valor excesivo',
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'solo tiene')
        self.assertFalse(MovimientoTienda.objects.exists())

    def test_crear_producto_registra_inventario_inicial(self):
        response = self.client.post(reverse('tienda:crear_producto'), {
            'nombre': 'Guantes de entrenamiento',
            'referencia': 'GUA-001',
            'descripcion': '',
            'precio_venta': '120000',
            'costo_unitario': '70000',
            'stock_minimo': '2',
            'stock_inicial': '6',
            'activo': 'on',
        })

        self.assertRedirects(response, reverse('tienda:configuracion'))
        producto = ProductoTienda.objects.get(referencia='GUA-001')
        self.assertEqual(producto.stock, 6)
        ajuste = producto.ajustes_inventario.get()
        self.assertEqual(ajuste.stock_anterior, 0)
        self.assertEqual(ajuste.stock_nuevo, 6)

    def test_varios_productos_pueden_tener_referencia_vacia(self):
        for nombre in ('Producto sin código 1', 'Producto sin código 2'):
            response = self.client.post(reverse('tienda:crear_producto'), {
                'nombre': nombre,
                'referencia': '',
                'descripcion': '',
                'precio_venta': '10000',
                'costo_unitario': '5000',
                'stock_minimo': '0',
                'stock_inicial': '0',
                'activo': 'on',
            })
            self.assertRedirects(response, reverse('tienda:configuracion'))

        self.assertEqual(
            ProductoTienda.objects.filter(referencia__isnull=True).count(),
            2,
        )

    def test_varios_productos_pueden_compartir_el_mismo_sku(self):
        response = self.client.post(reverse('tienda:crear_producto'), {
            'nombre': 'Camiseta academia segunda variante',
            'referencia': self.producto.referencia,
            'descripcion': '',
            'color': 'Azul',
            'talla': 'M',
            'precio_venta': '85000',
            'costo_unitario': '42000',
            'stock_minimo': '1',
            'stock_inicial': '3',
            'activo': 'on',
        })

        self.assertRedirects(response, reverse('tienda:configuracion'))
        self.assertEqual(
            ProductoTienda.objects.filter(referencia='CAM-001').count(),
            2,
        )

    def test_venta_descuenta_inventario_y_solo_afecta_tienda(self):
        response = self.client.post(reverse('tienda:registrar_venta'), {
            'producto': self.producto.id,
            'cantidad': '2',
            'cuenta': self.cuenta.id,
            'observaciones': 'Venta de prueba',
        })

        self.assertRedirects(response, reverse('tienda:panel'))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 8)
        movimiento = MovimientoTienda.objects.get()
        self.assertEqual(movimiento.tipo, MovimientoTienda.Tipos.INGRESO)
        self.assertEqual(movimiento.origen, MovimientoTienda.Origenes.VENTA)
        self.assertEqual(movimiento.valor, 160000)
        self.assertEqual(self.cuenta.saldo_actual, 360000)
        self.assertFalse(MovimientoFinanciero.objects.exists())

    def test_venta_rechaza_cantidad_superior_al_inventario(self):
        response = self.client.post(reverse('tienda:registrar_venta'), {
            'producto': self.producto.id,
            'cantidad': '20',
            'cuenta': self.cuenta.id,
            'observaciones': '',
        })

        self.assertEqual(response.status_code, 200)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 10)
        self.assertFalse(MovimientoTienda.objects.exists())
        self.assertContains(response, 'No hay inventario suficiente')

    def test_mensaje_de_venta_identifica_cada_producto_y_su_inventario(self):
        segundo_producto = ProductoTienda.objects.create(
            nombre='Rashguard pruebas',
            referencia='RASH-TEST',
            precio_venta=90000,
            costo_unitario=45000,
            stock=4,
        )

        primera_respuesta = self.client.post(
            reverse('tienda:registrar_venta'),
            {
                'producto': self.producto.id,
                'cantidad': '2',
                'cuenta': self.cuenta.id,
                'observaciones': '',
            },
            follow=True,
        )
        segunda_respuesta = self.client.post(
            reverse('tienda:registrar_venta'),
            {
                'producto': segundo_producto.id,
                'cantidad': '1',
                'cuenta': self.cuenta.id,
                'observaciones': '',
            },
            follow=True,
        )

        self.assertContains(
            primera_respuesta,
            'Venta registrada: Camiseta academia (2 unidades).',
        )
        self.assertContains(primera_respuesta, 'Inventario restante: 8.')
        self.assertContains(
            segunda_respuesta,
            'Venta registrada: Rashguard pruebas (1 unidad).',
        )
        self.assertContains(segunda_respuesta, 'Inventario restante: 3.')
        self.assertEqual(MovimientoTienda.objects.count(), 2)

    def test_compra_aumenta_inventario_y_registra_egreso(self):
        response = self.client.post(reverse('tienda:registrar_compra'), {
            'producto': self.producto.id,
            'cantidad': '5',
            'cuenta': self.cuenta.id,
            'costo_unitario': '45000',
            'actualizar_costo': 'on',
            'observaciones': '',
        })

        self.assertRedirects(response, reverse('tienda:panel'))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 15)
        self.assertEqual(self.producto.costo_unitario, Decimal('41666.67'))
        movimiento = MovimientoTienda.objects.get()
        self.assertEqual(movimiento.origen, MovimientoTienda.Origenes.COMPRA)
        self.assertEqual(movimiento.valor, 225000)
        ajuste = AjusteInventario.objects.get()
        self.assertEqual(ajuste.stock_anterior, 10)
        self.assertEqual(ajuste.stock_nuevo, 15)

    def test_gasto_general_no_modifica_inventario(self):
        response = self.client.post(reverse('tienda:registrar_gasto'), {
            'cuenta': self.cuenta.id,
            'concepto': 'Empaques',
            'valor': '30000',
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'observaciones': '',
        })

        self.assertRedirects(response, reverse('tienda:panel'))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 10)
        movimiento = MovimientoTienda.objects.get()
        self.assertEqual(movimiento.origen, MovimientoTienda.Origenes.GASTO)
        self.assertEqual(self.cuenta.saldo_actual, 170000)

    def test_ajuste_inventario_no_crea_movimiento_financiero(self):
        response = self.client.post(reverse('tienda:ajustar_inventario'), {
            'producto': self.producto.id,
            'tipo': AjusteInventario.Tipos.SALIDA,
            'cantidad': '3',
            'motivo': 'Producto dañado',
        })

        self.assertRedirects(response, reverse('tienda:panel'))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 7)
        self.assertFalse(MovimientoTienda.objects.exists())
        ajuste = AjusteInventario.objects.get()
        self.assertEqual(ajuste.stock_nuevo, 7)

    def test_producto_obsoleto_no_aparece_para_vender(self):
        response = self.client.post(
            reverse('tienda:cambiar_estado_producto', args=[self.producto.id])
        )

        self.assertRedirects(response, reverse('tienda:configuracion'))
        self.producto.refresh_from_db()
        self.assertFalse(self.producto.activo)
        form = VentaTiendaForm()
        self.assertNotIn(self.producto, form.fields['producto'].queryset)

    def test_panel_calcula_resultados_y_gastos_acumulados(self):
        MovimientoTienda.objects.create(
            cuenta=self.cuenta,
            tipo=MovimientoTienda.Tipos.INGRESO,
            origen=MovimientoTienda.Origenes.VENTA,
            concepto='Venta',
            valor=100000,
            producto=self.producto,
            cantidad=1,
        )
        MovimientoTienda.objects.create(
            cuenta=self.cuenta,
            tipo=MovimientoTienda.Tipos.EGRESO,
            origen=MovimientoTienda.Origenes.GASTO,
            concepto='Gasto',
            valor=25000,
        )

        response = self.client.get(reverse('tienda:panel'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ventas_mes'], 100000)
        self.assertEqual(response.context['egresos_mes'], 25000)
        self.assertEqual(response.context['egresos_acumulados'], 25000)
        self.assertEqual(response.context['utilidad_mes'], 75000)
        self.assertEqual(response.context['saldo_total'], 275000)
        self.assertEqual(response.context['valor_inventario'], 400000)
        self.assertContains(response, 'Dashboard de tienda')
        self.assertContains(response, 'graficoFlujoTienda')
        self.assertContains(response, 'graficoProductosTienda')
        self.assertEqual(response.context['ventas_flujo'][-1], 100000.0)
        self.assertEqual(response.context['egresos_flujo'][-1], 25000.0)
        self.assertEqual(
            response.context['labels_productos'],
            ['Camiseta academia'],
        )

    def test_configuracion_tienda_muestra_productos_y_cuentas(self):
        response = self.client.get(reverse('tienda:configuracion'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configuración de tienda')
        self.assertContains(response, self.producto.nombre)
        self.assertContains(response, self.cuenta.nombre)
        self.assertContains(response, reverse('tienda:panel'))

    def test_catalogo_gis_bross_se_importa_con_treinta_variantes(self):
        variantes = ProductoTienda.objects.filter(codigo_producto='100-101-001')

        self.assertEqual(variantes.count(), 30)
        self.assertEqual(variantes.values('referencia').distinct().count(), 30)
        self.assertEqual(variantes.values('codigo_barras').distinct().count(), 30)
        self.assertTrue(CategoriaProducto.objects.filter(codigo='100', nombre='Uniformes').exists())

    def test_dashboard_separa_resumenes_cop_y_usd(self):
        cuenta_usd = CuentaTienda.objects.create(
            nombre='Caja dólares', tipo=CuentaTienda.Tipos.EFECTIVO,
            moneda='USD', saldo_inicial=100,
        )
        MovimientoTienda.objects.create(
            cuenta=cuenta_usd, tipo=MovimientoTienda.Tipos.INGRESO,
            origen=MovimientoTienda.Origenes.GASTO, concepto='Entrada USD', valor=25,
        )

        response = self.client.get(reverse('tienda:panel'))

        resumenes = {item['codigo']: item for item in response.context['resumenes']}
        self.assertEqual(resumenes['USD']['saldo'], 125)
        self.assertEqual(resumenes['COP']['saldo'], 200000)

    def test_dashboard_muestra_separadores_de_miles_en_valores(self):
        response = self.client.get(reverse('tienda:panel'))

        self.assertContains(response, '$ 200.000,00')

    def test_categoria_tienda_es_independiente_y_conserva_movimientos(self):
        categoria = CategoriaMovimientoTienda.objects.create(
            nombre='Donaciones tienda pruebas',
            tipo=CategoriaMovimientoTienda.Tipos.INGRESO,
            naturaleza=CategoriaMovimientoTienda.Naturalezas.NO_OPERACIONAL,
        )
        datos = {
            'cuenta': self.cuenta.id,
            'categoria': categoria.id,
            'concepto': 'Aporte a la tienda',
            'valor': '40000',
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'observaciones': '',
            'soporte': SimpleUploadedFile(
                'aporte-tienda.pdf', b'%PDF soporte', content_type='application/pdf'
            ),
        }
        response = self.client.post(reverse('tienda:registrar_ingreso'), datos)

        self.assertRedirects(response, reverse('tienda:panel'))
        movimiento = MovimientoTienda.objects.get(concepto='Aporte a la tienda')
        self.assertEqual(movimiento.categoria, categoria)
        self.assertFalse(MovimientoFinanciero.objects.exists())
        panel = self.client.get(reverse('tienda:panel'))
        resumen = next(
            item for item in panel.context['resumenes'] if item['codigo'] == 'COP'
        )
        self.assertEqual(resumen['ingresos_no_operacionales'], 40000)
        self.assertEqual(resumen['ingresos_operacionales'], 0)

        categoria.activa = False
        categoria.save(update_fields=['activa'])
        self.assertEqual(movimiento.categoria_id, categoria.id)

    def test_venta_credito_exige_cliente_y_registra_cartera_sin_ingreso(self):
        cliente = ClienteTienda.objects.create(
            nombres='Cliente crédito', tipo_documento='CC', numero_documento='123456',
            telefono_whatsapp='573001234567', acepta_whatsapp=True,
        )
        response = self.client.post(reverse('tienda:registrar_venta'), {
            'producto': self.producto.id, 'cantidad': 2,
            'modalidad': VentaTienda.Modalidades.CREDITO,
            'cliente': cliente.id, 'descuento_porcentaje': 10,
            'fecha_vencimiento': (timezone.localdate() + timedelta(days=30)).isoformat(),
            'observaciones': '',
        })

        venta = VentaTienda.objects.get()
        self.assertRedirects(response, reverse('tienda:detalle_venta', args=[venta.id]))
        self.assertEqual(venta.total, 144000)
        self.assertEqual(venta.saldo_pendiente, 144000)
        self.assertFalse(MovimientoTienda.objects.exists())
        self.assertEqual(DetalleVentaTienda.objects.get().costo_unitario, 40000)

    def test_estudiante_aparece_como_comprador_y_se_vincula_a_la_venta(self):
        usuario = get_user_model().objects.create_user(
            username='comprador_alumno',
            password='ClaveSegura789!',
            first_name='Laura',
            last_name='Estudiante',
            email='laura@example.com',
            telefono='3007654321',
        )
        alumno = Alumno.objects.create(
            user=usuario,
            documento='ALUMNO-COMPRA-01',
            fecha_nacimiento=timezone.localdate() - timedelta(days=365 * 20),
            direccion='Dirección del estudiante',
        )

        formulario = self.client.get(reverse('tienda:registrar_venta'))
        self.assertContains(formulario, 'Estudiantes de la academia')
        self.assertContains(formulario, 'Laura Estudiante')
        self.assertContains(formulario, f'value="alumno:{alumno.id}"')

        response = self.client.post(reverse('tienda:registrar_venta'), {
            'producto': self.producto.id,
            'cantidad': 1,
            'modalidad': VentaTienda.Modalidades.CREDITO,
            'cliente': f'alumno:{alumno.id}',
            'descuento_porcentaje': 0,
            'numero_cuotas': 1,
            'fecha_vencimiento': (
                timezone.localdate() + timedelta(days=30)
            ).isoformat(),
            'observaciones': '',
        })

        venta = VentaTienda.objects.get()
        self.assertRedirects(
            response, reverse('tienda:detalle_venta', args=[venta.id])
        )
        self.assertEqual(venta.cliente.numero_documento, alumno.documento)
        self.assertEqual(venta.cliente.nombres, 'Laura Estudiante')
        self.assertEqual(venta.cliente.correo, 'laura@example.com')
        self.assertEqual(venta.cliente.telefono_whatsapp, '3007654321')

    def test_cartera_anterior_se_incorpora_sin_crear_venta_caja_o_inventario(self):
        fecha_deuda = timezone.localdate() - timedelta(days=90)
        fecha_vencida = timezone.localdate() - timedelta(days=30)

        response = self.client.post(reverse('tienda:registrar_cartera_inicial'), {
            'registrar_comprador': 'on',
            'comprador_nombres': 'Cliente cartera anterior',
            'comprador_tipo_documento': 'CC',
            'comprador_numero_documento': 'CARTERA-001',
            'comprador_whatsapp': '573001112233',
            'comprador_correo': 'cartera@example.com',
            'comprador_direccion': 'Dirección anterior',
            'moneda': 'COP',
            'saldo_inicial': '300000',
            'fecha_origen': fecha_deuda.isoformat(),
            'fecha_vencimiento': fecha_vencida.isoformat(),
            'numero_cuotas': '2',
            'referencia_externa': 'FAC-ANT-88',
            'observaciones': 'Saldo del sistema contable anterior',
        })

        venta = VentaTienda.objects.get()
        self.assertRedirects(
            response, reverse('tienda:detalle_venta', args=[venta.id])
        )
        self.assertEqual(
            venta.tipo_registro, VentaTienda.TiposRegistro.CARTERA_INICIAL
        )
        self.assertTrue(venta.numero.startswith('CI-'))
        self.assertEqual(venta.saldo_pendiente, Decimal('300000'))
        self.assertEqual(venta.referencia_externa, 'FAC-ANT-88')
        self.assertEqual(venta.cuotas.count(), 2)
        self.assertFalse(venta.detalles.exists())
        self.assertFalse(MovimientoTienda.objects.exists())
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 10)

        panel = self.client.get(reverse('tienda:panel'))
        resumen_cop = next(
            item for item in panel.context['resumenes'] if item['codigo'] == 'COP'
        )
        self.assertEqual(resumen_cop['ventas'], 0)
        self.assertEqual(resumen_cop['cartera'], Decimal('300000'))

    def test_cartera_anterior_admite_abonos_y_actualiza_saldo(self):
        cliente = ClienteTienda.objects.create(
            nombres='Cliente deuda inicial',
            tipo_documento='CC',
            numero_documento='CARTERA-ABONO',
        )
        response = self.client.post(reverse('tienda:registrar_cartera_inicial'), {
            'cliente': cliente.id,
            'moneda': 'COP',
            'saldo_inicial': '200000',
            'fecha_origen': (timezone.localdate() - timedelta(days=60)).isoformat(),
            'fecha_vencimiento': timezone.localdate().isoformat(),
            'numero_cuotas': '2',
            'referencia_externa': '',
            'observaciones': '',
        })
        venta = VentaTienda.objects.get()
        self.assertEqual(response.status_code, 302)

        self.client.post(reverse('tienda:registrar_abono', args=[venta.id]), {
            'cuenta': self.cuenta.id,
            'valor': '50000',
            'observaciones': 'Primer abono de cartera anterior',
        })

        venta.refresh_from_db()
        self.assertEqual(venta.estado, VentaTienda.Estados.PARCIAL)
        self.assertEqual(venta.saldo_pendiente, Decimal('150000'))
        movimiento = MovimientoTienda.objects.get()
        self.assertEqual(movimiento.origen, MovimientoTienda.Origenes.ABONO)
        self.assertEqual(movimiento.valor, Decimal('50000'))

    def test_abono_cierra_credito_y_habilita_paz_y_salvo(self):
        cliente = ClienteTienda.objects.create(
            nombres='Cliente paz y salvo', tipo_documento='CC', numero_documento='654321'
        )
        venta = VentaTienda.objects.create(
            cliente=cliente, modalidad='CREDITO', estado='PENDIENTE', moneda='COP',
            subtotal=80000, descuento=0, total=80000, saldo_pendiente=80000,
        )

        response = self.client.post(reverse('tienda:registrar_abono', args=[venta.id]), {
            'cuenta': self.cuenta.id, 'valor': 80000, 'observaciones': 'Pago final',
        })

        self.assertRedirects(response, reverse('tienda:detalle_venta', args=[venta.id]))
        venta.refresh_from_db()
        self.assertEqual(venta.estado, VentaTienda.Estados.PAGADA)
        self.assertEqual(venta.saldo_pendiente, 0)
        self.assertEqual(self.client.get(reverse('tienda:paz_y_salvo', args=[venta.id])).status_code, 200)

    def test_cuenta_inactiva_conserva_movimientos_y_no_aparece_en_formularios(self):
        MovimientoTienda.objects.create(
            cuenta=self.cuenta, tipo='EGRESO', origen='GASTO', concepto='Histórico', valor=1000,
        )
        self.client.post(reverse('tienda:cambiar_estado_cuenta', args=[self.cuenta.id]))

        self.cuenta.refresh_from_db()
        self.assertFalse(self.cuenta.activa)
        self.assertTrue(MovimientoTienda.objects.filter(cuenta=self.cuenta).exists())
        self.assertNotContains(self.client.get(reverse('tienda:registrar_gasto')), 'Caja tienda (COP)')

    def test_venta_permite_registrar_comprador_y_cuotas_en_el_mismo_formulario(self):
        response = self.client.post(reverse('tienda:registrar_venta'), {
            'producto': self.producto.id, 'cantidad': 2,
            'modalidad': VentaTienda.Modalidades.CREDITO,
            'numero_cuotas': 3,
            'fecha_vencimiento': (timezone.localdate() + timedelta(days=15)).isoformat(),
            'registrar_comprador': 'on',
            'comprador_nombres': 'Comprador en venta',
            'comprador_tipo_documento': 'CC',
            'comprador_numero_documento': '998877',
            'comprador_whatsapp': '573009998877',
            'comprador_correo': 'cliente@example.com',
            'comprador_acepta_whatsapp': 'on',
            'descuento_porcentaje': 0, 'observaciones': '',
        })

        venta = VentaTienda.objects.get()
        self.assertRedirects(response, reverse('tienda:detalle_venta', args=[venta.id]))
        self.assertEqual(venta.cliente.numero_documento, '998877')
        self.assertEqual(venta.numero_cuotas, 3)
        self.assertEqual(venta.cuotas.count(), 3)
        self.assertEqual(sum(c.valor for c in venta.cuotas.all()), venta.total)

    def test_abono_se_distribuye_entre_cuotas_en_orden(self):
        cliente = ClienteTienda.objects.create(
            nombres='Cliente cuotas', tipo_documento='CC', numero_documento='445566'
        )
        venta = VentaTienda.objects.create(
            cliente=cliente, modalidad='CREDITO', estado='PENDIENTE', moneda='COP',
            subtotal=160000, descuento=0, total=160000, saldo_pendiente=160000,
            fecha_vencimiento=timezone.localdate(), numero_cuotas=2,
        )
        for numero in (1, 2):
            CuotaVentaTienda.objects.create(
                venta=venta, numero=numero,
                fecha_vencimiento=timezone.localdate() + timedelta(days=30 * (numero - 1)),
                valor=80000, saldo=80000,
            )

        self.client.post(reverse('tienda:registrar_abono', args=[venta.id]), {
            'cuenta': self.cuenta.id, 'valor': 100000, 'observaciones': '',
        })

        cuotas = list(venta.cuotas.order_by('numero'))
        self.assertEqual(cuotas[0].estado, CuotaVentaTienda.Estados.PAGADA)
        self.assertEqual(cuotas[0].saldo, 0)
        self.assertEqual(cuotas[1].estado, CuotaVentaTienda.Estados.PARCIAL)
        self.assertEqual(cuotas[1].saldo, 60000)
        self.assertEqual(AplicacionAbonoCuota.objects.count(), 2)

    def test_abono_prioriza_cuota_elegida_y_distribuye_excedente(self):
        cliente = ClienteTienda.objects.create(
            nombres='Cliente elige cuota', tipo_documento='CC', numero_documento='CUOTA-SELECT'
        )
        venta = VentaTienda.objects.create(
            cliente=cliente, modalidad='CREDITO', estado='PENDIENTE', moneda='COP',
            subtotal=160000, descuento=0, total=160000, saldo_pendiente=160000,
            fecha_vencimiento=timezone.localdate(), numero_cuotas=2,
        )
        cuota_uno = CuotaVentaTienda.objects.create(
            venta=venta, numero=1, fecha_vencimiento=timezone.localdate(),
            valor=80000, saldo=80000,
        )
        cuota_dos = CuotaVentaTienda.objects.create(
            venta=venta, numero=2,
            fecha_vencimiento=timezone.localdate() + timedelta(days=30),
            valor=80000, saldo=80000,
        )

        self.client.post(reverse('tienda:registrar_abono', args=[venta.id]), {
            'cuota': cuota_dos.id, 'cuenta': self.cuenta.id,
            'valor': 100000, 'observaciones': 'Cuota dos más excedente',
        })

        cuota_uno.refresh_from_db()
        cuota_dos.refresh_from_db()
        self.assertEqual(cuota_dos.estado, CuotaVentaTienda.Estados.PAGADA)
        self.assertEqual(cuota_dos.saldo, 0)
        self.assertEqual(cuota_uno.estado, CuotaVentaTienda.Estados.PARCIAL)
        self.assertEqual(cuota_uno.saldo, 60000)
        aplicaciones = list(AplicacionAbonoCuota.objects.order_by('id'))
        self.assertEqual(aplicaciones[0].cuota, cuota_dos)
        self.assertEqual(aplicaciones[0].valor, 80000)
        self.assertEqual(aplicaciones[1].cuota, cuota_uno)
        self.assertEqual(aplicaciones[1].valor, 20000)

    def test_comprobante_se_descarga_como_pdf(self):
        venta = VentaTienda.objects.create(
            modalidad='CONTADO', estado='PAGADA', moneda='COP',
            subtotal=80000, descuento=0, total=80000, saldo_pendiente=0,
        )
        DetalleVentaTienda.objects.create(
            venta=venta, producto=self.producto, descripcion=self.producto.nombre,
            cantidad=1, precio_unitario=80000, costo_unitario=40000,
            descuento=0, total=80000,
        )

        response = self.client.get(reverse('tienda:descargar_comprobante', args=[venta.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))
        texto_pdf = ' '.join(
            pagina.extract_text() or '' for pagina in PdfReader(BytesIO(response.content)).pages
        )
        self.assertIn('Bross Fight Sports', texto_pdf)

    def test_venta_envia_pdf_automaticamente_si_comprador_tiene_correo(self):
        cliente = ClienteTienda.objects.create(
            nombres='Cliente correo', tipo_documento='CC', numero_documento='CORREO-1',
            correo='comprador@example.com',
        )

        response = self.client.post(reverse('tienda:registrar_venta'), {
            'producto': self.producto.id, 'cantidad': 1,
            'modalidad': VentaTienda.Modalidades.CONTADO,
            'cuenta': self.cuenta.id, 'cliente': cliente.id,
            'descuento_porcentaje': 0, 'observaciones': '',
        })

        venta = VentaTienda.objects.get()
        self.assertRedirects(response, reverse('tienda:detalle_venta', args=[venta.id]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['comprador@example.com'])
        self.assertIn('Bross Fight Sports', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].attachments[0][2], 'application/pdf')
        self.assertTrue(mail.outbox[0].attachments[0][1].startswith(b'%PDF'))
        venta.refresh_from_db()
        self.assertEqual(venta.email_enviado_a, 'comprador@example.com')
        self.assertIsNotNone(venta.fecha_envio_correo)
        self.assertEqual(venta.error_envio_correo, '')

    def test_comprobante_puede_reenviarse_por_correo(self):
        cliente = ClienteTienda.objects.create(
            nombres='Cliente reenvío', tipo_documento='CC', numero_documento='CORREO-2',
            correo='reenvio@example.com',
        )
        venta = VentaTienda.objects.create(
            cliente=cliente, modalidad='CONTADO', estado='PAGADA', moneda='COP',
            subtotal=80000, descuento=0, total=80000, saldo_pendiente=0,
        )
        DetalleVentaTienda.objects.create(
            venta=venta, producto=self.producto, descripcion=self.producto.nombre,
            cantidad=1, precio_unitario=80000, costo_unitario=40000,
            descuento=0, total=80000,
        )

        response = self.client.post(
            reverse('tienda:enviar_comprobante_correo', args=[venta.id]), follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(response, 'Comprobante enviado a reenvio@example.com')
