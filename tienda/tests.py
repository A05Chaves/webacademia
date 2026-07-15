from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from finanzas.models import MovimientoFinanciero

from .forms import VentaTiendaForm
from .models import AjusteInventario, CuentaTienda, MovimientoTienda, ProductoTienda


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

    def test_panel_requiere_usuario_del_personal(self):
        self.client.logout()

        response = self.client.get(reverse('tienda:panel'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

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
        self.assertEqual(self.producto.costo_unitario, 45000)
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
