from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from gestion.forms import GastoForm, PagoProgramadoForm, TransferenciaForm
from pagos.models import Evento

from .models import CategoriaFinanciera, CuentaFinanciera, MovimientoFinanciero, PagoProgramado


class FormulariosContablesTests(TestCase):
    def setUp(self):
        self.cuenta_activa = CuentaFinanciera.objects.create(
            nombre='Caja activa',
            tipo=CuentaFinanciera.Tipos.EFECTIVO,
            saldo_inicial=100000,
        )
        self.cuenta_inactiva = CuentaFinanciera.objects.create(
            nombre='Caja cerrada',
            tipo=CuentaFinanciera.Tipos.EFECTIVO,
            activa=False,
        )
        self.categoria_egreso = CategoriaFinanciera.objects.create(
            nombre='Arriendo',
            tipo=CategoriaFinanciera.Tipos.EGRESO,
        )
        self.categoria_ingreso = CategoriaFinanciera.objects.create(
            nombre='Ventas',
            tipo=CategoriaFinanciera.Tipos.INGRESO,
        )
        self.categoria_inactiva = CategoriaFinanciera.objects.create(
            nombre='Categoría cerrada',
            tipo=CategoriaFinanciera.Tipos.EGRESO,
            activa=False,
        )

    def test_gasto_solo_ofrece_cuentas_y_categorias_validas(self):
        form = GastoForm()

        self.assertQuerySetEqual(
            form.fields['cuenta'].queryset,
            [self.cuenta_activa],
        )
        self.assertQuerySetEqual(
            form.fields['categoria'].queryset,
            [self.categoria_egreso],
        )

    def test_gasto_rechaza_valor_no_positivo(self):
        form = GastoForm(data={
            'cuenta': self.cuenta_activa.id,
            'categoria': self.categoria_egreso.id,
            'concepto': 'Gasto inválido',
            'valor': '-100',
            'fecha': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'observaciones': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('valor', form.errors)

    def test_pago_programado_rechaza_valor_no_positivo(self):
        form = PagoProgramadoForm(data={
            'concepto': 'Pago inválido',
            'valor': '0',
            'fecha_vencimiento': (timezone.localdate() + timedelta(days=1)).isoformat(),
            'cuenta_pago': self.cuenta_activa.id,
            'observaciones': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('valor', form.errors)

    def test_transferencia_rechaza_valor_no_positivo(self):
        form = TransferenciaForm(data={
            'cuenta_origen': self.cuenta_activa.id,
            'cuenta_destino': self.cuenta_inactiva.id,
            'valor': '-1',
            'concepto': 'Transferencia inválida',
            'observaciones': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('valor', form.errors)


class VistasContablesTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='administrador_contable',
            password='clave-segura-pruebas',
            is_staff=True,
        )
        self.client.force_login(self.usuario)
        self.cuenta = CuentaFinanciera.objects.create(
            nombre='Cuenta pruebas contables',
            tipo=CuentaFinanciera.Tipos.BANCO,
            saldo_inicial=500000,
        )

    def test_detalle_financiero_tolera_filtros_invalidos(self):
        response = self.client.get(
            reverse('gestion:detalle_financiero'),
            {'mes': 'no-es-un-mes', 'anio': 'sin-año'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['mes'], timezone.localdate().month)
        self.assertEqual(response.context['anio'], timezone.localdate().year)

    def test_dashboard_discrimina_ingresos_y_gastos_por_evento(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Open Galeras 2026',
            descripcion='Torneo de prueba contable',
            fecha_inicio=timezone.now(),
            lugar='Dojo principal',
            precio_estudiante=80000,
            precio_externo=100000,
        )
        MovimientoFinanciero.objects.create(
            cuenta=self.cuenta,
            tipo=MovimientoFinanciero.Tipos.INGRESO,
            evento=evento,
            concepto='Inscripción Open Galeras 2026',
            valor=300000,
        )
        MovimientoFinanciero.objects.create(
            cuenta=self.cuenta,
            tipo=MovimientoFinanciero.Tipos.EGRESO,
            evento=evento,
            concepto='Medallas Open Galeras 2026',
            valor=90000,
        )

        response = self.client.get(reverse('gestion:dashboard'))

        self.assertEqual(response.status_code, 200)
        resumen = response.context['eventos_financieros'][0]
        self.assertEqual(resumen.nombre, 'Open Galeras 2026')
        self.assertEqual(resumen.ingresos_evento, 300000)
        self.assertEqual(resumen.gastos_evento, 90000)
        self.assertEqual(resumen.resultado_evento, 210000)
        self.assertContains(response, 'Resultado financiero por evento')
        self.assertContains(response, 'Open Galeras 2026')

    def test_pago_cancelado_no_genera_movimiento(self):
        pago = PagoProgramado.objects.create(
            concepto='Pago cancelado',
            valor=80000,
            fecha_vencimiento=timezone.localdate(),
            estado=PagoProgramado.Estados.CANCELADO,
            cuenta_pago=self.cuenta,
        )

        response = self.client.post(
            reverse('gestion:pagar_pago_programado', args=[pago.id])
        )

        self.assertRedirects(response, reverse('gestion:dashboard'))
        self.assertFalse(MovimientoFinanciero.objects.exists())

    def test_pago_programado_no_se_contabiliza_dos_veces(self):
        pago = PagoProgramado.objects.create(
            concepto='Pago pendiente',
            valor=80000,
            fecha_vencimiento=timezone.localdate(),
            cuenta_pago=self.cuenta,
        )
        url = reverse('gestion:pagar_pago_programado', args=[pago.id])

        self.client.post(url)
        self.client.post(url)

        pago.refresh_from_db()
        self.assertEqual(pago.estado, PagoProgramado.Estados.PAGADO)
        self.assertEqual(MovimientoFinanciero.objects.count(), 1)

    def test_datos_de_grafica_se_serializan_de_forma_segura(self):
        categoria = CategoriaFinanciera.objects.create(
            nombre="Gasto </script> 'especial'",
            tipo=CategoriaFinanciera.Tipos.EGRESO,
        )
        MovimientoFinanciero.objects.create(
            cuenta=self.cuenta,
            tipo=MovimientoFinanciero.Tipos.EGRESO,
            categoria=categoria,
            concepto='Prueba gráfica',
            valor=1000,
        )

        response = self.client.get(reverse('gestion:detalle_financiero'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'etiquetas-gastos-categoria')
        self.assertContains(response, r'\u003C/script\u003E')

    def test_transferencia_mueve_saldos_sin_inflar_resultados(self):
        destino = CuentaFinanciera.objects.create(
            nombre='Cuenta destino contable',
            tipo=CuentaFinanciera.Tipos.BANCO,
            saldo_inicial=100000,
        )

        response = self.client.post(
            reverse('gestion:registrar_transferencia'),
            {
                'cuenta_origen': self.cuenta.id,
                'cuenta_destino': destino.id,
                'valor': '50000',
                'concepto': 'Movimiento entre cuentas',
                'observaciones': '',
            },
        )

        self.assertRedirects(response, reverse('gestion:dashboard'))
        self.assertEqual(self.cuenta.saldo_actual, 450000)
        self.assertEqual(destino.saldo_actual, 150000)

        dashboard = self.client.get(reverse('gestion:dashboard'))
        self.assertEqual(dashboard.context['ingresos_mes'], 0)
        self.assertEqual(dashboard.context['gastos_mes'], 0)

        detalle = self.client.get(reverse('gestion:detalle_financiero'))
        self.assertEqual(detalle.context['total_ingresos'], 0)
        self.assertEqual(detalle.context['total_egresos'], 0)

    def test_dashboard_grafica_flujo_y_saldos_usa_valores_monetarios(self):
        MovimientoFinanciero.objects.create(
            cuenta=self.cuenta,
            tipo=MovimientoFinanciero.Tipos.INGRESO,
            concepto='Ingreso del mes',
            valor=120000,
        )
        MovimientoFinanciero.objects.create(
            cuenta=self.cuenta,
            tipo=MovimientoFinanciero.Tipos.EGRESO,
            concepto='Gasto del mes',
            valor=40000,
        )

        response = self.client.get(reverse('gestion:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ingresos_flujo'][-1], 120000.0)
        self.assertEqual(response.context['gastos_flujo'][-1], 40000.0)
        self.assertEqual(
            response.context['labels_cuentas'],
            ['Cuenta pruebas contables'],
        )
        self.assertEqual(response.context['saldos_cuentas'], [580000.0])
        self.assertContains(response, 'graficoFlujoCaja')
        self.assertContains(response, 'graficoSaldosCuenta')

    def test_configuracion_permite_crear_cuenta_con_saldo_inicial(self):
        response = self.client.post(
            reverse('gestion:configurar_cuentas'),
            {
                'nombre': 'Caja principal',
                'tipo': CuentaFinanciera.Tipos.EFECTIVO,
                'saldo_inicial': '350000',
                'activa': 'on',
            },
        )

        self.assertRedirects(
            response,
            reverse('gestion:configurar_cuentas'),
        )
        cuenta = CuentaFinanciera.objects.get(nombre='Caja principal')
        self.assertEqual(cuenta.saldo_inicial, 350000)
        self.assertEqual(cuenta.saldo_actual, 350000)

    def test_editar_saldo_inicial_no_modifica_movimientos(self):
        MovimientoFinanciero.objects.create(
            cuenta=self.cuenta,
            tipo=MovimientoFinanciero.Tipos.INGRESO,
            concepto='Movimiento existente',
            valor=50000,
        )

        response = self.client.post(
            reverse('gestion:editar_cuenta_financiera', args=[self.cuenta.id]),
            {
                'nombre': self.cuenta.nombre,
                'tipo': self.cuenta.tipo,
                'saldo_inicial': '700000',
                'activa': 'on',
            },
        )

        self.assertRedirects(
            response,
            reverse('gestion:configurar_cuentas'),
        )
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo_inicial, 700000)
        self.assertEqual(self.cuenta.saldo_actual, 750000)
        self.assertEqual(self.cuenta.movimientos.count(), 1)

    def test_configuracion_cuentas_requiere_personal_autorizado(self):
        self.client.logout()

        response = self.client.get(reverse('gestion:configurar_cuentas'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_categoria_no_operacional_se_inhabilita_sin_perder_historial(self):
        categoria = CategoriaFinanciera.objects.create(
            nombre='Donaciones academia',
            tipo=CategoriaFinanciera.Tipos.INGRESO,
            naturaleza=CategoriaFinanciera.Naturalezas.NO_OPERACIONAL,
        )
        movimiento = MovimientoFinanciero.objects.create(
            cuenta=self.cuenta,
            categoria=categoria,
            tipo=MovimientoFinanciero.Tipos.INGRESO,
            concepto='Aporte histórico',
            valor=50000,
        )

        response = self.client.post(
            reverse('gestion:editar_categoria_financiera', args=[categoria.id]),
            {
                'nombre': categoria.nombre,
                'tipo': categoria.tipo,
                'naturaleza': categoria.naturaleza,
                'descripcion': 'Categoría inhabilitada',
            },
        )

        self.assertRedirects(
            response, reverse('gestion:configurar_categorias_financieras')
        )
        categoria.refresh_from_db()
        movimiento.refresh_from_db()
        self.assertFalse(categoria.activa)
        self.assertEqual(movimiento.categoria, categoria)

    def test_ingreso_no_operacional_exige_soporte_y_aparece_en_dashboard(self):
        categoria = CategoriaFinanciera.objects.create(
            nombre='Aporte extraordinario',
            tipo=CategoriaFinanciera.Tipos.INGRESO,
            naturaleza=CategoriaFinanciera.Naturalezas.NO_OPERACIONAL,
        )
        datos = {
            'cuenta': self.cuenta.id,
            'categoria': categoria.id,
            'concepto': 'Donación externa',
            'valor': '75000',
            'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'observaciones': '',
        }
        sin_soporte = self.client.post(
            reverse('gestion:registrar_ingreso_manual'), datos
        )
        self.assertEqual(sin_soporte.status_code, 200)
        self.assertFalse(MovimientoFinanciero.objects.exists())

        datos['soporte'] = SimpleUploadedFile(
            'aporte.pdf', b'%PDF-1.4 soporte', content_type='application/pdf'
        )
        con_soporte = self.client.post(
            reverse('gestion:registrar_ingreso_manual'), datos
        )
        self.assertRedirects(con_soporte, reverse('gestion:dashboard'))
        dashboard = self.client.get(reverse('gestion:dashboard'))
        self.assertEqual(dashboard.context['ingresos_no_operacionales_mes'], 75000)
        self.assertEqual(dashboard.context['ingresos_operacionales_mes'], 0)

    def test_otro_ingreso_crea_categoria_reutilizable_sin_exigir_evento(self):
        response = self.client.post(
            reverse('gestion:registrar_ingreso_manual'),
            {
                'cuenta': self.cuenta.id,
                'categoria': '',
                'nueva_categoria': 'Aportes especiales',
                'naturaleza_nueva_categoria': (
                    CategoriaFinanciera.Naturalezas.OPERACIONAL
                ),
                'evento': '',
                'concepto': 'Aporte de aliado',
                'valor': '60000',
                'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
                'observaciones': '',
            },
        )

        self.assertRedirects(response, reverse('gestion:dashboard'))
        categoria = CategoriaFinanciera.objects.get(nombre='APORTES ESPECIALES')
        movimiento = MovimientoFinanciero.objects.get(concepto='Aporte de aliado')
        self.assertEqual(categoria.tipo, CategoriaFinanciera.Tipos.INGRESO)
        self.assertEqual(
            categoria.naturaleza,
            CategoriaFinanciera.Naturalezas.OPERACIONAL,
        )
        self.assertEqual(movimiento.categoria, categoria)
        self.assertIsNone(movimiento.evento)

        formulario_futuro = self.client.get(
            reverse('gestion:registrar_ingreso_manual')
        )
        self.assertContains(formulario_futuro, 'APORTES ESPECIALES')
        self.assertContains(formulario_futuro, 'Sin evento relacionado')

        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Seminario contable',
            descripcion='Evento relacionado con el ingreso',
            fecha_inicio=timezone.now() + timedelta(days=10),
            lugar='Academia',
            precio_estudiante=50000,
            precio_externo=70000,
        )
        ingreso_evento = self.client.post(
            reverse('gestion:registrar_ingreso_manual'),
            {
                'cuenta': self.cuenta.id,
                'categoria': categoria.id,
                'nueva_categoria': '',
                'evento': evento.id,
                'concepto': 'Ingreso del seminario',
                'valor': '90000',
                'fecha': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
                'observaciones': '',
            },
        )
        self.assertRedirects(ingreso_evento, reverse('gestion:dashboard'))
        self.assertEqual(
            MovimientoFinanciero.objects.get(
                concepto='Ingreso del seminario'
            ).evento,
            evento,
        )
