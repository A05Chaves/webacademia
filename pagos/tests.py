import base64
import json
from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageDraw

from alumnos.models import Alumno
from finanzas.models import CuentaFinanciera
from planes.models import Plan, Suscripcion
from gestion.forms import CategoriaEventoForm, EventoForm, PagoAlumnoForm, PagoForm
from gestion.models import ConfiguracionHome

from .models import (
    AcademiaCompetidora, CategoriaEvento, Evento, InscripcionEvento,
    JornadaEvento, LlaveCategoriaEvento, MetodoPagoQR, Pago, Promocion,
)
from .services import marcar_posible_duplicado


def imagen_prueba(nombre='foto.png'):
    salida = BytesIO()
    imagen = Image.new('RGB', (120, 120), 'white')
    ImageDraw.Draw(imagen).line((10, 100, 110, 20), fill='black', width=5)
    imagen.save(salida, format='PNG')
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type='image/png')


def firma_visible():
    archivo = imagen_prueba('firma.png')
    return 'data:image/png;base64,' + base64.b64encode(archivo.read()).decode()


class PagosAcademiaNuevosFlujosTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.override = self.settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media.cleanup)
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_user(
            username='admin-nuevos-pagos', password='clave-admin', is_staff=True
        )
        self.usuario = Usuario.objects.create_user(
            username='alumno-nuevos-pagos', password='clave-alumno',
            email='alumno@galeras.test', telefono='3001112233',
        )
        self.alumno = Alumno.objects.create(
            user=self.usuario,
            documento='EST-900',
            fecha_nacimiento=timezone.localdate().replace(year=1995),
            nombre_acudiente='Acudiente Prueba',
            documento_acudiente='ACU-777',
        )
        self.plan = Plan.objects.create(
            nombre='Mensual pruebas nuevas', precio=120000, duracion_dias=30
        )
        self.cuenta = CuentaFinanciera.objects.create(
            nombre='Cuenta pagos nuevos', tipo=CuentaFinanciera.Tipos.BANCO
        )
        self.metodo = MetodoPagoQR.objects.create(
            nombre='QR pagos nuevos', titular='Galeras BJJ',
            imagen_qr=SimpleUploadedFile('qr.png', b'qr'),
            cuenta_financiera=self.cuenta,
        )

    def nuevo_pago(self, nombre='pago.pdf', contenido=b'%PDF-comprobante'):
        pago = Pago(
            alumno=self.alumno,
            plan=self.plan,
            metodo_qr=self.metodo,
            valor=120000,
            comprobante=SimpleUploadedFile(nombre, contenido),
            referencia_pago='REF-900',
            pagador_documento='ACU-777',
        )
        marcar_posible_duplicado(pago)
        pago.save()
        return pago

    def test_registro_publico_exitoso_muestra_confirmacion_grande(self):
        response = self.client.post(reverse('gestion:registrar_pago_alumno'), {
            'username': 'alumno-nuevos-pagos',
            'password': 'clave-alumno',
            'plan': self.plan.id,
            'metodo_qr': self.metodo.id,
            'valor': '120000',
            'referencia_pago': 'REF-VISIBLE-1',
            'comprobante': SimpleUploadedFile(
                'pago-visible.pdf', b'%PDF-1.4\n%%EOF'
            ),
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'payment-feedback-overlay')
        self.assertContains(response, 'Pago registrado')
        self.assertContains(response, 'Queda pendiente de validación')
        self.assertTrue(Pago.objects.filter(
            alumno=self.alumno,
            referencia_pago='REF-VISIBLE-1',
        ).exists())

    def test_estudiante_con_sesion_registra_pago_sin_repetir_credenciales(self):
        self.client.force_login(self.usuario)
        response = self.client.post(reverse('gestion:registrar_pago_alumno'), {
            'plan': self.plan.id,
            'metodo_qr': self.metodo.id,
            'valor': '120000',
            'referencia_pago': 'REF-SESION-1',
            'comprobante': SimpleUploadedFile(
                'pago-sesion.pdf', b'%PDF-1.4\n%%EOF'
            ),
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Pago.objects.filter(
            alumno=self.alumno,
            referencia_pago='REF-SESION-1',
        ).exists())
        self.assertIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'Valor pagado:')
        self.assertContains(response, '120.000')
        self.assertContains(response, f'Plan seleccionado: {self.plan.nombre}')
        self.assertContains(response, 'Registrarás el pago como')
        self.assertContains(response, 'password-visibility-toggle')

    def test_registro_publico_fallido_muestra_error_grande(self):
        response = self.client.post(reverse('gestion:registrar_pago_alumno'), {
            'username': 'alumno-nuevos-pagos',
            'password': 'incorrecta',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'payment-feedback-overlay')
        self.assertContains(response, 'No se registró el pago')
        self.assertContains(response, 'Usuario o contraseña incorrectos')

    def test_marca_archivo_o_referencia_repetidos(self):
        primero = self.nuevo_pago()
        segundo = self.nuevo_pago(nombre='copia.pdf')

        self.assertFalse(primero.posible_duplicado)
        self.assertTrue(segundo.posible_duplicado)
        self.assertEqual(segundo.duplicado_de, primero)

    def test_aprobacion_usa_fecha_real_y_cuenta_dia_inicial(self):
        pago = self.nuevo_pago()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('gestion:validar_pago', args=[pago.id]),
            {
                'estado': Pago.Estados.APROBADO,
                'fecha_inicio': '2026-07-01',
                'fecha_inicio_manual': 'on',
            },
        )

        self.assertRedirects(response, reverse('gestion:lista_pagos'))
        pago.refresh_from_db()
        self.assertEqual(pago.suscripcion.fecha_inicio.isoformat(), '2026-07-01')
        self.assertEqual(pago.suscripcion.fecha_vencimiento.isoformat(), '2026-07-30')
        self.assertTrue(pago.numero_comprobante.startswith('CP-'))

    def test_renovacion_con_dias_activos_inicia_despues_del_vencimiento(self):
        hoy = timezone.localdate()
        vigente = Suscripcion.objects.create(
            alumno=self.alumno,
            plan=self.plan,
            fecha_inicio=hoy - timedelta(days=10),
            fecha_vencimiento=hoy + timedelta(days=12),
            estado=Suscripcion.Estados.ACTIVA,
        )
        pago = self.nuevo_pago(nombre='renovacion.pdf')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:validar_pago', args=[pago.id]),
            {'estado': Pago.Estados.APROBADO},
        )

        self.assertRedirects(response, reverse('gestion:lista_pagos'))
        pago.refresh_from_db()
        vigente.refresh_from_db()
        self.assertEqual(
            pago.suscripcion.fecha_inicio,
            vigente.fecha_vencimiento + timedelta(days=1),
        )
        self.assertEqual(vigente.estado, Suscripcion.Estados.ACTIVA)

    def test_fecha_enviada_sin_edicion_manual_no_reemplaza_la_suscripcion(self):
        hoy = timezone.localdate()
        vigente = Suscripcion.objects.create(
            alumno=self.alumno,
            plan=self.plan,
            fecha_inicio=hoy - timedelta(days=5),
            fecha_vencimiento=hoy + timedelta(days=15),
            estado=Suscripcion.Estados.ACTIVA,
        )
        pago = self.nuevo_pago(nombre='fecha-formulario-obsoleta.pdf')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:validar_pago', args=[pago.id]),
            {
                'estado': Pago.Estados.APROBADO,
                'fecha_inicio': '2026-06-01',
            },
        )

        self.assertRedirects(response, reverse('gestion:lista_pagos'))
        pago.refresh_from_db()
        self.assertEqual(
            pago.suscripcion.fecha_inicio,
            vigente.fecha_vencimiento + timedelta(days=1),
        )

    def test_renovacion_vencida_continua_desde_el_vencimiento_anterior(self):
        hoy = timezone.localdate()
        vencida = Suscripcion.objects.create(
            alumno=self.alumno,
            plan=self.plan,
            fecha_inicio=hoy - timedelta(days=40),
            fecha_vencimiento=hoy - timedelta(days=10),
            estado=Suscripcion.Estados.VENCIDA,
        )
        self.alumno.estado = Alumno.Estados.VENCIDO
        self.alumno.save(update_fields=['estado'])
        pago = self.nuevo_pago(nombre='renovacion-vencida.pdf')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:validar_pago', args=[pago.id]),
            {'estado': Pago.Estados.APROBADO},
        )

        self.assertRedirects(response, reverse('gestion:lista_pagos'))
        pago.refresh_from_db()
        self.alumno.refresh_from_db()
        self.assertEqual(
            pago.suscripcion.fecha_inicio,
            vencida.fecha_vencimiento + timedelta(days=1),
        )
        self.assertEqual(
            pago.suscripcion.fecha_vencimiento,
            vencida.fecha_vencimiento + timedelta(days=self.plan.duracion_dias),
        )
        self.assertEqual(pago.suscripcion.estado, Suscripcion.Estados.ACTIVA)
        self.assertEqual(self.alumno.estado, Alumno.Estados.ACTIVO)

    def test_aprobacion_corrige_suscripcion_vencida_que_seguia_activa(self):
        hoy = timezone.localdate()
        vencida_sin_actualizar = Suscripcion.objects.create(
            alumno=self.alumno,
            plan=self.plan,
            fecha_inicio=hoy - timedelta(days=40),
            fecha_vencimiento=hoy - timedelta(days=10),
            estado=Suscripcion.Estados.ACTIVA,
        )
        pago = self.nuevo_pago(nombre='renovacion-estado-obsoleto.pdf')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:validar_pago', args=[pago.id]),
            {'estado': Pago.Estados.APROBADO},
        )

        self.assertRedirects(response, reverse('gestion:lista_pagos'))
        pago.refresh_from_db()
        vencida_sin_actualizar.refresh_from_db()
        self.assertEqual(
            vencida_sin_actualizar.estado,
            Suscripcion.Estados.VENCIDA,
        )
        self.assertEqual(pago.estado, Pago.Estados.APROBADO)
        self.assertEqual(pago.suscripcion.estado, Suscripcion.Estados.ACTIVA)
        self.assertEqual(
            pago.suscripcion.fecha_inicio,
            vencida_sin_actualizar.fecha_vencimiento + timedelta(days=1),
        )

    def test_cuenta_inactiva_no_aparece_en_formularios_de_pago(self):
        self.cuenta.activa = False
        self.cuenta.save(update_fields=['activa'])

        self.assertNotIn(
            self.metodo,
            PagoAlumnoForm().fields['metodo_qr'].queryset,
        )
        self.assertNotIn(
            self.metodo,
            PagoForm().fields['metodo_qr'].queryset,
        )

    def test_no_aprueba_pago_si_su_cuenta_fue_inhabilitada(self):
        pago = self.nuevo_pago()
        self.cuenta.activa = False
        self.cuenta.save(update_fields=['activa'])
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:validar_pago', args=[pago.id]),
            {'estado': Pago.Estados.APROBADO, 'fecha_inicio': '2026-07-01'},
        )

        self.assertRedirects(
            response, reverse('gestion:validar_pago', args=[pago.id])
        )
        pago.refresh_from_db()
        self.assertEqual(pago.estado, Pago.Estados.PENDIENTE)
        self.assertIsNone(pago.suscripcion)

    def test_historial_filtra_por_documento_acudiente(self):
        self.nuevo_pago()
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('gestion:lista_pagos'), {'documento': 'ACU-777'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'REF-900')

    def test_historial_muestra_cuenta_donde_se_consigno(self):
        self.nuevo_pago()
        self.client.force_login(self.admin)

        response = self.client.get(reverse('gestion:lista_pagos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cuenta consignada')
        self.assertContains(response, self.cuenta.nombre)
        self.assertContains(response, self.metodo.nombre)

    def test_promocion_publicada_aparece_en_home(self):
        hoy = timezone.localdate()
        promocion = Promocion.objects.create(
            nombre='Promoción visible', descripcion='Beneficio especial',
            plan=self.plan,
            tipo_beneficio=Promocion.TiposBeneficio.PORCENTAJE,
            valor_beneficio=10,
            fecha_inicio=hoy - timedelta(days=1),
            fecha_fin=hoy + timedelta(days=5),
            publicada_home=True,
        )
        response = self.client.get(reverse('gestion:home_publica'))
        self.assertContains(response, promocion.nombre)
        self.assertContains(response, 'Aplicar a la promoción')

    def test_evento_publicado_aparece_con_registro(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Seminario visible',
            descripcion='Seminario de pruebas',
            fecha_inicio=timezone.now() + timedelta(days=10),
            lugar='Galeras BJJ',
            precio_estudiante=50000,
            precio_externo=70000,
            publicada_home=True,
        )
        response = self.client.get(reverse('gestion:home_publica'))
        self.assertContains(response, evento.nombre)
        self.assertContains(response, 'Registrarme')

    def test_administrador_crea_seminario_con_jornadas_y_tarifas_distintas(self):
        self.client.force_login(self.admin)
        inicio = timezone.localtime(timezone.now()) + timedelta(days=10)
        formato = '%Y-%m-%dT%H:%M'
        response = self.client.post(reverse('gestion:crear_evento'), {
            'tipo': Evento.Tipos.SEMINARIO,
            'nombre': 'Seminario por jornadas',
            'descripcion': 'Adultos e infantil en horarios distintos',
            'fecha_inicio': inicio.strftime(formato),
            'lugar': 'Galeras BJJ',
            'precio_estudiante': '0',
            'precio_externo': '0',
            'publico': Evento.Publicos.TODOS,
            'alcance_torneo': Evento.AlcancesTorneo.INTERNO,
            'consentimiento_evento': 'Consentimiento del seminario.',
            'reglamento_adultos': 'Reglamento del seminario para adultos.',
            'reglamento_menores': 'Reglamento infantil del seminario.',
            'orden': '10',
            'activo': 'on',
            'jornadas-TOTAL_FORMS': '2',
            'jornadas-INITIAL_FORMS': '0',
            'jornadas-MIN_NUM_FORMS': '0',
            'jornadas-MAX_NUM_FORMS': '1000',
            'jornadas-0-nombre': 'Jornada adultos',
            'jornadas-0-publico': JornadaEvento.Publicos.ADULTOS,
            'jornadas-0-fecha_inicio': inicio.strftime(formato),
            'jornadas-0-fecha_fin': (inicio + timedelta(hours=2)).strftime(formato),
            'jornadas-0-precio_estudiante': '60000',
            'jornadas-0-precio_externo': '80000',
            'jornadas-0-cupo_maximo': '30',
            'jornadas-0-orden': '1',
            'jornadas-0-activa': 'on',
            'jornadas-1-nombre': 'Jornada infantil',
            'jornadas-1-publico': JornadaEvento.Publicos.MENORES,
            'jornadas-1-fecha_inicio': (inicio + timedelta(hours=3)).strftime(formato),
            'jornadas-1-fecha_fin': (inicio + timedelta(hours=5)).strftime(formato),
            'jornadas-1-precio_estudiante': '40000',
            'jornadas-1-precio_externo': '55000',
            'jornadas-1-cupo_maximo': '25',
            'jornadas-1-orden': '2',
            'jornadas-1-activa': 'on',
        })

        self.assertRedirects(response, reverse('gestion:promociones_eventos'))
        evento = Evento.objects.get(nombre='Seminario por jornadas')
        self.assertEqual(evento.jornadas.count(), 2)
        self.assertEqual(
            evento.jornadas.get(publico=JornadaEvento.Publicos.ADULTOS).precio_externo,
            80000,
        )

    def test_jornada_infantil_de_seminario_no_exige_documentos_legales(self):
        self.client.force_login(self.admin)
        inicio = timezone.localtime(timezone.now()) + timedelta(days=10)
        formato = '%Y-%m-%dT%H:%M'

        response = self.client.post(reverse('gestion:crear_evento'), {
            'tipo': Evento.Tipos.SEMINARIO,
            'nombre': 'Seminario con validación infantil',
            'descripcion': 'Prueba de documentos por jornada',
            'fecha_inicio': inicio.strftime(formato),
            'lugar': 'Galeras BJJ',
            'precio_estudiante': '0',
            'precio_externo': '0',
            'publico': Evento.Publicos.ADULTOS,
            'alcance_torneo': Evento.AlcancesTorneo.INTERNO,
            'consentimiento_evento': 'Consentimiento configurado.',
            'reglamento_adultos': 'Reglamento para adultos.',
            'reglamento_menores': '',
            'orden': '10',
            'activo': 'on',
            'jornadas-TOTAL_FORMS': '1',
            'jornadas-INITIAL_FORMS': '0',
            'jornadas-MIN_NUM_FORMS': '0',
            'jornadas-MAX_NUM_FORMS': '1000',
            'jornadas-0-nombre': 'Jornada infantil',
            'jornadas-0-publico': JornadaEvento.Publicos.MENORES,
            'jornadas-0-fecha_inicio': inicio.strftime(formato),
            'jornadas-0-fecha_fin': (inicio + timedelta(hours=2)).strftime(formato),
            'jornadas-0-precio_estudiante': '0',
            'jornadas-0-precio_externo': '0',
            'jornadas-0-orden': '1',
            'jornadas-0-activa': 'on',
        })

        self.assertRedirects(response, reverse('gestion:promociones_eventos'))
        evento = Evento.objects.get(nombre='Seminario con validación infantil')
        self.assertEqual(evento.jornadas.count(), 1)
        self.assertEqual(evento.documentos_legales_faltantes, [])

    def test_seminario_legado_sin_documentos_sigue_recibiendo_inscripciones(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Seminario legado incompleto',
            descripcion='Evento creado antes de la validación por jornadas',
            fecha_inicio=timezone.now() + timedelta(days=10),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            publico=Evento.Publicos.ADULTOS,
            consentimiento_evento='Consentimiento configurado.',
            reglamento_adultos='Reglamento para adultos.',
            reglamento_menores='',
            publicada_home=True,
        )
        JornadaEvento.objects.create(
            evento=evento,
            nombre='Jornada infantil',
            publico=JornadaEvento.Publicos.MENORES,
            fecha_inicio=evento.fecha_inicio,
            precio_estudiante=0,
            precio_externo=0,
        )
        InscripcionEvento.objects.create(
            evento=evento,
            participante_nombre='Participante existente',
            participante_documento='LEGADO-1',
            fecha_nacimiento=timezone.localdate().replace(year=2015),
            correo='legado@example.com',
            telefono='3000000000',
        )

        response = self.client.get(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Consentimiento informado')
        self.assertNotContains(response, 'Reglamento del evento')
        self.assertEqual(evento.inscripciones.count(), 1)

        self.client.force_login(self.admin)
        panel = self.client.get(reverse('gestion:promociones_eventos'))
        self.assertNotContains(panel, 'Falta: reglamento para menores y acudientes')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_seminario_reporta_valor_con_descuento_y_pago_se_aprueba(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Seminario pagado',
            descripcion='Seminario para validar pagos',
            fecha_inicio=timezone.now() + timedelta(days=10),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            consentimiento_evento='Acepto participar en este seminario.',
            reglamento_adultos='Reglamento visible para participantes adultos.',
            reglamento_menores='Reglamento visible para menores y acudientes.',
        )
        jornada = JornadaEvento.objects.create(
            evento=evento,
            nombre='Jornada adultos',
            publico=JornadaEvento.Publicos.ADULTOS,
            fecha_inicio=evento.fecha_inicio,
            precio_estudiante=60000,
            precio_externo=80000,
        )

        pagina = self.client.get(
            reverse('gestion:inscribirse_evento', args=[evento.id])
        )
        self.assertNotContains(pagina, 'name="peso"')
        self.assertContains(pagina, 'Valor pagado')
        self.assertNotContains(pagina, 'Consentimiento informado')
        self.assertNotContains(pagina, 'Reglamento del evento')
        self.assertNotContains(pagina, 'name="acepta_consentimiento"')
        self.assertNotContains(pagina, 'name="acepta_reglamento"')
        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Visitante Seminario',
                'participante_documento': 'SEM-EXT-1',
                'fecha_nacimiento': '1990-05-10',
                'correo': 'seminario@example.com',
                'telefono': '3009876543',
                'jornada': jornada.id,
                'metodo_qr': self.metodo.id,
                'valor_pagado': '65000',
                'referencia_pago': 'SEM-DESCUENTO-1',
                'comprobante': SimpleUploadedFile(
                    'seminario.pdf', b'%PDF-1.4\n%%EOF'
                ),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'payment-feedback-overlay')
        self.assertContains(response, 'Valor pagado: $ 65.000')
        inscripcion = InscripcionEvento.objects.get(evento=evento)
        self.assertIsNone(inscripcion.peso)
        self.assertEqual(inscripcion.jornada, jornada)
        self.assertEqual(inscripcion.tarifa_publicada, 80000)
        self.assertEqual(inscripcion.pago.valor, 65000)
        self.assertEqual(inscripcion.texto_consentimiento, '')
        self.assertEqual(inscripcion.texto_reglamento, '')

        self.client.force_login(self.admin)
        historial = self.client.get(
            reverse('gestion:inscripciones_evento', args=[evento.id])
        )
        self.assertContains(historial, 'Total: 1')
        self.assertContains(historial, 'Jornada adultos: 1')
        edicion = self.client.get(
            reverse('gestion:editar_inscripcion_evento', args=[inscripcion.id])
        )
        self.assertEqual(edicion.status_code, 200)
        self.assertContains(edicion, jornada.nombre)
        self.assertNotContains(edicion, 'name="peso"')

        aprobacion = self.client.post(
            reverse('gestion:validar_pago', args=[inscripcion.pago_id]),
            {'estado': Pago.Estados.APROBADO},
            follow=True,
        )

        self.assertEqual(aprobacion.status_code, 200)
        inscripcion.refresh_from_db()
        inscripcion.pago.refresh_from_db()
        self.assertEqual(inscripcion.estado, InscripcionEvento.Estados.CONFIRMADA)
        self.assertEqual(inscripcion.pago.estado, Pago.Estados.APROBADO)
        self.assertContains(aprobacion, 'Valor validado: $ 65.000')

    def crear_torneo_gratuito(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Torneo categorías',
            descripcion='Torneo de prueba para llaves',
            fecha_inicio=timezone.now() + timedelta(days=20),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            alcance_torneo=Evento.AlcancesTorneo.ABIERTO,
            consentimiento_evento='Acepto los riesgos y reglas de este torneo.',
            reglamento_adultos='Reglamento competitivo para adultos.',
            reglamento_menores='Reglamento competitivo para menores y acudientes.',
        )
        categoria = CategoriaEvento.objects.create(
            evento=evento,
            nombre='Adulto ligero',
            genero=CategoriaEvento.Generos.MIXTA,
            edad_minima=18,
            peso_maximo=76,
            nivel='Principiante',
        )
        return evento, categoria

    def test_formulario_categoria_aclara_el_orden_de_aparicion(self):
        form = CategoriaEventoForm()
        self.assertEqual(form.fields['orden'].label, 'Orden de aparición')
        self.assertIn(
            'No lanza combates automáticamente',
            form.fields['orden'].help_text,
        )

    def test_panel_eventos_oculta_vencidos_y_permite_buscar_historial(self):
        vigente, _ = self.crear_torneo_gratuito()
        vencido = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Torneo histórico Pasto',
            descripcion='Evento finalizado',
            fecha_inicio=timezone.now() - timedelta(days=5),
            fecha_fin=timezone.now() - timedelta(days=4),
            lugar='Pasto',
            precio_estudiante=0,
            precio_externo=0,
        )
        categoria = CategoriaEvento.objects.create(
            evento=vencido, nombre='Adultos cinturón azul'
        )
        InscripcionEvento.objects.create(
            evento=vencido,
            categoria_evento=categoria,
            participante_nombre='Atleta Histórico',
            participante_documento='REC-2026-01',
            fecha_nacimiento=timezone.localdate().replace(year=1992),
            correo='record@example.com',
            telefono='3000000000',
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        self.client.force_login(self.admin)
        url = reverse('gestion:promociones_eventos')

        actuales = self.client.get(url)
        self.assertContains(actuales, vigente.nombre)
        self.assertNotContains(actuales, vencido.nombre)
        self.assertContains(actuales, 'Eventos vigentes')

        historial = self.client.get(url, {
            'estado': 'historicos', 'q': 'REC-2026-01'
        })
        self.assertContains(historial, vencido.nombre)
        self.assertContains(historial, 'Historial de eventos')
        self.assertContains(
            historial,
            reverse('gestion:inscripciones_evento', args=[vencido.id]),
        )
        self.assertNotContains(historial, vigente.nombre)

    def test_evento_gratuito_oculta_campos_de_pago(self):
        evento, categoria = self.crear_torneo_gratuito()

        response = self.client.get(
            reverse('gestion:inscribirse_evento', args=[evento.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, categoria.nombre)
        self.assertNotContains(response, 'name="metodo_qr"')
        self.assertNotContains(response, 'name="referencia_pago"')
        self.assertNotContains(response, 'name="comprobante"')

    def test_torneo_gratuito_confirma_categoria_sin_crear_pago(self):
        evento, categoria = self.crear_torneo_gratuito()

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Competidor Uno',
                'participante_documento': 'TOR-001',
                'fecha_nacimiento': '1995-05-10',
                'correo': 'competidor@example.com',
                'telefono': '3001234567',
                'categoria_evento': categoria.id,
                'peso': '74.50',
                'academia_origen': 'Academia visitante',
                'logo_academia': imagen_prueba('logo-visitante.png'),
                'foto_participante': imagen_prueba(),
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(
            evento=evento, participante_documento='TOR-001'
        )
        self.assertEqual(inscripcion.categoria_evento, categoria)
        self.assertEqual(inscripcion.estado, InscripcionEvento.Estados.CONFIRMADA)
        self.assertEqual(inscripcion.academia_origen, 'Academia visitante')
        self.assertTrue(inscripcion.foto_participante.name)
        self.assertEqual(
            inscripcion.texto_consentimiento, evento.consentimiento_evento
        )
        self.assertTrue(inscripcion.firma_base64.startswith('data:image/png;base64,'))
        self.assertIsNone(inscripcion.pago)
        self.assertFalse(Pago.objects.filter(tipo=Pago.Tipos.EVENTO).exists())

    def test_participante_reutiliza_academia_y_logo_registrados(self):
        evento, categoria = self.crear_torneo_gratuito()
        academia = AcademiaCompetidora.objects.create(
            nombre='Equipo ya registrado',
            logo=imagen_prueba('equipo-registrado.png'),
        )

        pagina = self.client.get(
            reverse('gestion:inscribirse_evento', args=[evento.id])
        )
        self.assertContains(pagina, 'Equipo ya registrado')
        self.assertContains(pagina, 'Mi academia no aparece en la lista')

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Participante con academia existente',
                'participante_documento': 'ACA-EXISTE-1',
                'fecha_nacimiento': '1995-05-10',
                'correo': 'academia-existente@example.com',
                'telefono': '3005554433',
                'academia_registrada': academia.id,
                'foto_participante': imagen_prueba('participante-existente.png'),
                'categoria_evento': categoria.id,
                'peso': '70',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(
            evento=evento, participante_documento='ACA-EXISTE-1'
        )
        self.assertEqual(inscripcion.academia_equipo, academia)
        self.assertEqual(inscripcion.academia_origen, academia.nombre)
        academia.refresh_from_db()
        self.assertTrue(academia.logo.name)
        self.assertEqual(
            inscripcion.texto_consentimiento, evento.consentimiento_evento
        )
        self.assertTrue(inscripcion.firma_base64.startswith('data:image/png;base64,'))
        self.assertIsNone(inscripcion.pago)
        self.assertFalse(Pago.objects.filter(tipo=Pago.Tipos.EVENTO).exists())

    def test_categoria_rechaza_peso_fuera_del_rango(self):
        evento, categoria = self.crear_torneo_gratuito()

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Competidor Pesado',
                'participante_documento': 'TOR-002',
                'fecha_nacimiento': '1990-01-01',
                'correo': 'pesado@example.com',
                'telefono': '3007654321',
                'categoria_evento': categoria.id,
                'peso': '80',
                'academia_origen': 'Academia visitante',
                'logo_academia': imagen_prueba('logo-peso.png'),
                'foto_participante': imagen_prueba(),
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'El peso supera el permitido')
        self.assertFalse(InscripcionEvento.objects.filter(evento=evento).exists())

    def test_llaves_reciben_solo_inscritos_confirmados_de_la_categoria(self):
        evento, categoria = self.crear_torneo_gratuito()
        otra_categoria = CategoriaEvento.objects.create(
            evento=evento, nombre='Adulto pesado', edad_minima=18,
        )
        datos = {
            'evento': evento,
            'fecha_nacimiento': timezone.localdate().replace(year=1990),
            'correo': 'llaves@example.com',
            'telefono': '3000000000',
            'acepta_consentimiento': True,
        }
        academia_norte = AcademiaCompetidora.objects.create(
            nombre='Academia Norte', logo=imagen_prueba('logo-norte.png')
        )
        InscripcionEvento.objects.create(
            **datos, categoria_evento=categoria,
            participante_nombre='Ana Confirmada', participante_documento='LL-1',
            academia_origen='Academia Norte',
            academia_equipo=academia_norte,
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        InscripcionEvento.objects.create(
            **datos, categoria_evento=categoria,
            participante_nombre='Pendiente No Cargar', participante_documento='LL-2',
            estado=InscripcionEvento.Estados.PENDIENTE,
        )
        InscripcionEvento.objects.create(
            **datos, categoria_evento=otra_categoria,
            participante_nombre='Otra Categoria', participante_documento='LL-3',
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        self.admin.is_superuser = True
        self.admin.save(update_fields=['is_superuser'])
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('gestion:cronometro_lucha'),
            {'evento': evento.id, 'categoria': categoria.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Ana Confirmada — Academia Norte', response.context['participantes_llave']
        )
        self.assertEqual(
            response.context['logos_llave']['Ana Confirmada — Academia Norte'],
            academia_norte.logo.url,
        )
        self.client.logout()
        logo_response = self.client.get(academia_norte.logo.url)
        self.assertEqual(logo_response.status_code, 200)
        logo_response.close()
        self.assertNotContains(response, 'Pendiente No Cargar')
        self.assertNotContains(response, 'Otra Categoria')
        self.assertContains(response, f'luchaBracket-categoria-{categoria.id}')

    def test_orden_del_torneo_reune_combates_de_varias_llaves(self):
        evento, categoria = self.crear_torneo_gratuito()
        otra = CategoriaEvento.objects.create(
            evento=evento, nombre='Adulto pesado', edad_minima=18, orden=20,
        )
        for indice, categoria_llave in enumerate((categoria, otra), start=1):
            LlaveCategoriaEvento.objects.create(
                categoria=categoria_llave,
                datos={
                    'names': [f'ROJO {indice}', f'AZUL {indice}'],
                    'configuredSize': 2,
                    'capacity': 2,
                    'rounds': [[{
                        'p1': f'ROJO {indice}',
                        'p2': f'AZUL {indice}',
                        'winner': None,
                    }]],
                },
                actualizada_por=self.admin,
            )
        self.admin.is_superuser = True
        self.admin.save(update_fields=['is_superuser'])
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('gestion:cronometro_lucha'), {'evento': evento.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['combates_disponibles']), 2)
        self.assertContains(response, 'Orden rotativo de combates')
        self.assertContains(response, 'ROJO 1 vs AZUL 1')
        self.assertContains(response, 'ROJO 2 vs AZUL 2')

        directo = self.client.get(reverse('gestion:cronometro_lucha'), {
            'evento': evento.id,
            'categoria': categoria.id,
            'ronda': 0,
            'combate': 0,
        })
        self.assertEqual(
            directo.context['combate_solicitado'], {'ronda': 0, 'combate': 0}
        )
        self.assertEqual(
            directo.context['siguiente_combate']['categoria'].id, otra.id
        )
        self.assertContains(directo, 'SIGUIENTE:')
        self.assertContains(directo, 'Cargar siguiente')
        self.assertContains(directo, 'ROJO 2 vs AZUL 2')
        self.assertContains(directo, 'function loadRequestedFight')

    def test_categoria_sin_inscripciones_se_puede_eliminar(self):
        evento, categoria = self.crear_torneo_gratuito()
        self.client.force_login(self.admin)
        response = self.client.post(reverse(
            'gestion:eliminar_categoria_evento', args=[evento.id, categoria.id]
        ))
        self.assertRedirects(response, reverse('gestion:promociones_eventos'))
        self.assertFalse(CategoriaEvento.objects.filter(id=categoria.id).exists())

    def test_categoria_con_inscripciones_no_se_elimina(self):
        evento, categoria = self.crear_torneo_gratuito()
        InscripcionEvento.objects.create(
            evento=evento,
            categoria_evento=categoria,
            participante_nombre='Competidor protegido',
            participante_documento='CAT-PROTEGIDA',
            fecha_nacimiento=timezone.localdate().replace(year=1990),
            correo='protegido@example.com',
            telefono='3000000000',
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse(
            'gestion:eliminar_categoria_evento', args=[evento.id, categoria.id]
        ))
        self.assertRedirects(response, reverse(
            'gestion:editar_categoria_evento', args=[evento.id, categoria.id]
        ))
        self.assertTrue(CategoriaEvento.objects.filter(id=categoria.id).exists())

    def test_torneo_interno_recupera_datos_solo_con_documento(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Torneo interno',
            descripcion='Competencia de estudiantes',
            fecha_inicio=timezone.now() + timedelta(days=15),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            alcance_torneo=Evento.AlcancesTorneo.INTERNO,
            consentimiento_evento='Consentimiento exclusivo del torneo interno.',
            reglamento_adultos='Reglamento interno para adultos.',
            reglamento_menores='Reglamento interno para menores y acudientes.',
        )
        categoria = CategoriaEvento.objects.create(
            evento=evento, nombre='Interna adultos', edad_minima=18,
        )

        consulta = self.client.get(
            reverse('gestion:datos_estudiante_torneo', args=[evento.id]),
            {'documento': self.alumno.documento},
        )
        self.assertEqual(consulta.status_code, 200)
        self.assertEqual(consulta.json()['nombre'], str(self.alumno))
        self.assertTrue(consulta.json()['ficha_completa'])

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_documento': self.alumno.documento,
                'categoria_evento': categoria.id,
                'peso': '70',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(evento=evento)
        self.assertEqual(inscripcion.alumno, self.alumno)
        self.assertEqual(inscripcion.participante_nombre, str(self.alumno))
        self.assertEqual(inscripcion.correo, self.usuario.email)
        self.assertEqual(
            inscripcion.texto_consentimiento, evento.consentimiento_evento
        )
        self.assertEqual(inscripcion.texto_reglamento, evento.reglamento_adultos)
        self.assertTrue(inscripcion.firma_base64.startswith('data:image/png;base64,'))
        self.assertIsNotNone(inscripcion.fecha_firma)

    def test_inscripcion_de_menor_guarda_su_reglamento_especifico(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Torneo abierto infantil',
            descripcion='Competencia para menores',
            fecha_inicio=timezone.now() + timedelta(days=25),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            publico=Evento.Publicos.MENORES,
            alcance_torneo=Evento.AlcancesTorneo.ABIERTO,
            consentimiento_evento='Consentimiento firmado por el acudiente.',
            reglamento_menores='Reglamento infantil especial.',
        )
        categoria = CategoriaEvento.objects.create(
            evento=evento, nombre='Infantil', edad_maxima=17,
        )

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Competidor Menor',
                'participante_documento': 'MEN-001',
                'fecha_nacimiento': '2013-06-01',
                'correo': 'acudiente@example.com',
                'telefono': '3004445566',
                'academia_origen': 'Academia Infantil',
                'logo_academia': imagen_prueba('logo-infantil.png'),
                'foto_participante': imagen_prueba(),
                'acudiente_nombre': 'Acudiente Responsable',
                'acudiente_documento': 'ACU-MEN-1',
                'acudiente_telefono': '3009998877',
                'categoria_evento': categoria.id,
                'peso': '40',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(evento=evento)
        self.assertEqual(inscripcion.texto_reglamento, evento.reglamento_menores)
        self.assertTrue(inscripcion.acepta_reglamento)
        self.assertEqual(inscripcion.acudiente_nombre, 'Acudiente Responsable')

    def test_imagen_del_evento_es_publica_sin_exponer_fotos_de_participantes(self):
        evento, _ = self.crear_torneo_gratuito()
        evento.imagen.save('afiche-torneo.png', imagen_prueba(), save=True)

        imagen_response = self.client.get(evento.imagen.url)
        self.assertEqual(imagen_response.status_code, 200)
        imagen_response.close()

        ruta_privada = default_storage.save(
            'eventos/participantes/foto-privada.png',
            ContentFile(imagen_prueba().read()),
        )
        privada_response = self.client.get('/media/' + ruta_privada)
        self.assertEqual(privada_response.status_code, 302)
        self.assertIn('/login/', privada_response.url)

        self.client.force_login(self.admin)
        privada_admin = self.client.get('/media/' + ruta_privada)
        self.assertEqual(privada_admin.status_code, 200)
        privada_admin.close()

    def test_video_corto_del_torneo_aparece_en_el_home(self):
        evento, _ = self.crear_torneo_gratuito()
        evento.publicada_home = True
        evento.video = SimpleUploadedFile(
            'promocion.mp4',
            b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom',
            content_type='video/mp4',
        )
        evento.save()

        response = self.client.get(reverse('gestion:home_publica'))

        self.assertContains(response, evento.video.url)
        self.assertContains(response, 'home-publication-video')
        video_response = self.client.get(evento.video.url)
        self.assertEqual(video_response.status_code, 200)
        video_response.close()

    def test_prioridad_define_si_evento_aparece_antes_del_video_promocional(self):
        configuracion = ConfiguracionHome.objects.create(
            video_promo_url='https://www.youtube.com/watch?v=abcdefghijk',
            orden_video_promocional=50,
            activo=True,
        )
        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Seminario prioritario',
            descripcion='Debe aparecer antes que el video promocional.',
            fecha_inicio=timezone.now() + timedelta(days=5),
            fecha_fin=timezone.now() + timedelta(days=6),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            publicada_home=True,
            orden=5,
        )

        response = self.client.get(reverse('gestion:home_publica'))

        elementos = response.context['elementos_carrusel_home']
        self.assertEqual(
            [elemento['tipo'] for elemento in elementos],
            ['EVENTO', 'VIDEO_PROMOCIONAL'],
        )
        self.assertEqual(elementos[0]['objeto'], evento)
        self.assertContains(
            response,
            'class="carousel-item active" data-tipo="EVENTO" data-prioridad="5"',
        )

        self.client.force_login(self.admin)
        cambio = self.client.post(reverse('gestion:configurar_home'), {
            'video_promo_url': configuracion.video_promo_url,
            'orden_video_promocional': 1,
            'playlist_youtube_url': '',
            'activo': 'on',
        })
        self.assertRedirects(cambio, reverse('gestion:configurar_home'))
        configuracion.refresh_from_db()
        self.assertEqual(configuracion.orden_video_promocional, 1)

        actualizado = self.client.get(reverse('gestion:home_publica'))
        self.assertEqual(
            actualizado.context['elementos_carrusel_home'][0]['tipo'],
            'VIDEO_PROMOCIONAL',
        )
        configuracion_page = self.client.get(reverse('gestion:configurar_home'))
        self.assertContains(
            configuracion_page, 'id="id_orden_video_promocional"'
        )

    def test_evento_en_curso_permanece_visible_hasta_su_fecha_final(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Evento actualmente en curso',
            descripcion='Debe continuar en el carrusel',
            fecha_inicio=timezone.now() - timedelta(days=1),
            fecha_fin=timezone.now() + timedelta(days=2),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            publicada_home=True,
        )

        response = self.client.get(reverse('gestion:home_publica'))

        self.assertContains(response, evento.nombre)

    def test_banner_con_imagen_solo_muestra_acciones_y_habilita_llaves_un_dia_antes(self):
        evento, _ = self.crear_torneo_gratuito()
        evento.descripcion = 'Texto que no debe cubrir el afiche del torneo'
        evento.imagen = imagen_prueba('afiche-acciones.png')
        evento.publicada_home = True
        evento.fecha_inicio = timezone.now() + timedelta(days=2)
        evento.save()

        anticipado = self.client.get(reverse('gestion:home_publica'))
        self.assertContains(anticipado, 'Registrarme')
        self.assertNotContains(anticipado, 'Ver llaves')
        self.assertNotContains(anticipado, evento.descripcion)

        evento.fecha_inicio = timezone.now() + timedelta(hours=12)
        evento.save(update_fields=['fecha_inicio'])
        habilitado = self.client.get(reverse('gestion:home_publica'))
        self.assertContains(habilitado, 'Registrarme')
        self.assertContains(habilitado, 'Ver llaves')

    def test_llave_guardada_por_admin_se_puede_consultar_publicamente(self):
        evento, categoria = self.crear_torneo_gratuito()
        evento.fecha_inicio = timezone.now() + timedelta(hours=12)
        evento.publicada_home = True
        evento.save(update_fields=['fecha_inicio', 'publicada_home'])
        datos = {
            'names': ['ANA — EQUIPO A', 'LUZ — EQUIPO B'],
            'configuredSize': 4,
            'capacity': 4,
            'rounds': [[{
                'p1': 'ANA — EQUIPO A',
                'p2': 'LUZ — EQUIPO B',
                'winner': None,
            }]],
        }
        self.admin.is_superuser = True
        self.admin.save(update_fields=['is_superuser'])
        self.client.force_login(self.admin)
        guardado = self.client.post(
            reverse('gestion:guardar_llave_categoria', args=[categoria.id]),
            data=json.dumps({'datos': datos}),
            content_type='application/json',
        )
        self.assertEqual(guardado.status_code, 200)
        self.assertTrue(
            LlaveCategoriaEvento.objects.filter(categoria=categoria).exists()
        )

        self.client.logout()
        publica = self.client.get(
            reverse('gestion:llaves_evento_publicas', args=[evento.id])
        )
        self.assertEqual(publica.status_code, 200)
        self.assertContains(publica, 'ANA')
        self.assertContains(publica, 'LUZ')
        self.assertContains(publica, str(categoria.nombre))

    def test_fechas_de_inscripcion_son_independientes_del_evento(self):
        inicio_evento = timezone.localtime(timezone.now()) + timedelta(days=10)
        fin_evento = inicio_evento + timedelta(days=2)
        apertura = inicio_evento - timedelta(days=20)
        cierre = inicio_evento + timedelta(days=1)
        formato = '%Y-%m-%dT%H:%M'
        form = EventoForm(data={
            'tipo': Evento.Tipos.SEMINARIO,
            'nombre': 'Seminario con inscripción independiente',
            'descripcion': 'Prueba de calendario',
            'fecha_inicio': inicio_evento.strftime(formato),
            'fecha_fin': fin_evento.strftime(formato),
            'fecha_inicio_inscripcion': apertura.strftime(formato),
            'fecha_limite_inscripcion': cierre.strftime(formato),
            'lugar': 'Galeras BJJ',
            'precio_estudiante': '0',
            'precio_externo': '0',
            'publico': Evento.Publicos.TODOS,
            'alcance_torneo': Evento.AlcancesTorneo.INTERNO,
            'consentimiento_evento': '',
            'reglamento_adultos': '',
            'reglamento_menores': '',
            'orden': '10',
            'activo': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_evento_no_recibe_inscripciones_antes_de_su_apertura(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Inscripción futura',
            descripcion='Aún no abre',
            fecha_inicio=timezone.now() + timedelta(days=20),
            fecha_inicio_inscripcion=timezone.now() + timedelta(days=2),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=10),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
        )

        self.assertFalse(evento.disponible)

    def test_correccion_del_formulario_exige_una_firma_nueva(self):
        evento, categoria = self.crear_torneo_gratuito()
        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Participante por corregir',
                'participante_documento': 'COR-001',
                'fecha_nacimiento': '1995-05-10',
                'correo': 'corregir@example.com',
                'telefono': '3005556677',
                'academia_origen': 'Academia Corrección',
                'logo_academia': imagen_prueba('logo-correccion.png'),
                'foto_participante': imagen_prueba(),
                'categoria_evento': categoria.id,
                # Se omite deliberadamente el peso.
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('peso', response.context['form'].errors)
        self.assertEqual(response.context['form']['firma_base64'].value(), '')
        self.assertFalse(InscripcionEvento.objects.filter(evento=evento).exists())

    def test_participante_de_18_anos_es_adulto_y_no_exige_acudiente(self):
        evento, categoria = self.crear_torneo_gratuito()
        hoy = timezone.localdate()
        nacimiento_adulto = hoy.replace(year=hoy.year - 18)
        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Adulto Recién Cumplido',
                'participante_documento': 'ADU-018',
                'fecha_nacimiento': nacimiento_adulto.isoformat(),
                'correo': 'adulto18@example.com',
                'telefono': '3001231818',
                'academia_origen': 'Academia Adultos',
                'logo_academia': imagen_prueba('logo-adultos.png'),
                'foto_participante': imagen_prueba(),
                'categoria_evento': categoria.id,
                'peso': '70',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(evento=evento)
        self.assertEqual(inscripcion.acudiente_nombre, '')
        self.assertEqual(inscripcion.texto_reglamento, evento.reglamento_adultos)

    def test_administrador_puede_mover_participante_a_otra_categoria(self):
        evento, categoria_origen = self.crear_torneo_gratuito()
        categoria_destino = CategoriaEvento.objects.create(
            evento=evento,
            nombre='Adulto intermedio',
            edad_minima=18,
            peso_minimo=65,
            peso_maximo=80,
        )
        inscripcion = InscripcionEvento.objects.create(
            evento=evento,
            categoria_evento=categoria_origen,
            categoria=str(categoria_origen),
            participante_nombre='Competidor Movible',
            participante_documento='MOV-001',
            fecha_nacimiento=timezone.localdate().replace(year=1995),
            correo='mover@example.com',
            telefono='3007778899',
            academia_origen='Academia Móvil',
            peso=72,
            acepta_reglamento=True,
            acepta_consentimiento=True,
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:mover_inscripcion_categoria', args=[inscripcion.id]),
            {'categoria_evento': categoria_destino.id},
        )

        self.assertRedirects(
            response, reverse('gestion:inscripciones_evento', args=[evento.id])
        )
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.categoria_evento, categoria_destino)
        categoria_destino.refresh_from_db()
        self.assertEqual(inscripcion.categoria, str(categoria_destino))

    def test_administrador_puede_forzar_movimiento_fuera_del_rango_de_peso(self):
        evento, categoria_origen = self.crear_torneo_gratuito()
        categoria_destino = CategoriaEvento.objects.create(
            evento=evento,
            nombre='Peso superior administrativo',
            peso_minimo=80,
            peso_maximo=90,
        )
        inscripcion = InscripcionEvento.objects.create(
            evento=evento,
            categoria_evento=categoria_origen,
            categoria=str(categoria_origen),
            participante_nombre='Competidor fuera de rango',
            participante_documento='MOV-FORZADO',
            fecha_nacimiento=timezone.localdate().replace(year=1995),
            correo='forzado@example.com',
            telefono='3009998877',
            academia_origen='Academia Manual',
            peso=56,
            acepta_reglamento=True,
            acepta_consentimiento=True,
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:mover_inscripcion_categoria', args=[inscripcion.id]),
            {'categoria_evento': categoria_destino.id},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.categoria_evento, categoria_destino)
        self.assertContains(response, 'fue movido manualmente')

    def test_administrador_puede_editar_datos_del_participante(self):
        evento, categoria = self.crear_torneo_gratuito()
        firma_original = firma_visible()
        inscripcion = InscripcionEvento.objects.create(
            evento=evento,
            categoria_evento=categoria,
            categoria=str(categoria),
            participante_nombre='Nombre por corregir',
            participante_documento='EDIT-001',
            fecha_nacimiento=timezone.localdate().replace(year=1995),
            correo='anterior@example.com',
            telefono='3000000000',
            academia_origen='Academia anterior',
            peso=70,
            firma_base64=firma_original,
            acepta_reglamento=True,
            acepta_consentimiento=True,
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        self.client.force_login(self.admin)

        pagina = self.client.get(
            reverse('gestion:editar_inscripcion_evento', args=[inscripcion.id])
        )
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Guardar cambios')
        self.assertContains(pagina, 'no reemplaza ni modifica')

        response = self.client.post(
            reverse('gestion:editar_inscripcion_evento', args=[inscripcion.id]),
            {
                'participante_nombre': 'Nombre Corregido',
                'participante_documento': 'EDIT-001',
                'fecha_nacimiento': inscripcion.fecha_nacimiento.isoformat(),
                'correo': 'corregido@example.com',
                'telefono': '3112223344',
                'academia_origen': 'Academia corregida',
                'acudiente_nombre': '',
                'acudiente_documento': '',
                'acudiente_telefono': '',
                'categoria_evento': categoria.id,
                'peso': '72.50',
                'estado': InscripcionEvento.Estados.CONFIRMADA,
            },
        )

        self.assertRedirects(
            response, reverse('gestion:inscripciones_evento', args=[evento.id])
        )
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.participante_nombre, 'Nombre Corregido')
        self.assertEqual(inscripcion.correo, 'corregido@example.com')
        self.assertEqual(str(inscripcion.peso), '72.50')
        self.assertEqual(inscripcion.academia_origen, 'Academia corregida')
        self.assertEqual(inscripcion.firma_base64, firma_original)

    def test_participante_puede_inscribirse_en_regular_y_superior(self):
        evento, categoria_regular = self.crear_torneo_gratuito()
        categoria_superior = CategoriaEvento.objects.create(
            evento=evento,
            nombre='División superior',
            tipo_categoria=CategoriaEvento.TiposCategoria.SUPERIOR,
            edad_minima=18,
            peso_maximo=88,
        )

        def datos(categoria, incluir_logo=False):
            data = {
                'participante_nombre': 'Competidor Doble',
                'participante_documento': 'DOB-001',
                'fecha_nacimiento': '1994-03-10',
                'correo': 'doble@example.com',
                'telefono': '3001212121',
                'academia_origen': 'Academia Doble',
                'foto_participante': imagen_prueba('competidor-doble.png'),
                'categoria_evento': categoria.id,
                'peso': '74',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            }
            if incluir_logo:
                data['logo_academia'] = imagen_prueba('logo-doble.png')
            return data

        primera = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            datos(categoria_regular, incluir_logo=True),
        )
        segunda = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            datos(categoria_superior),
        )

        self.assertRedirects(primera, reverse('gestion:home_publica'))
        self.assertRedirects(segunda, reverse('gestion:home_publica'))
        inscripciones = InscripcionEvento.objects.filter(
            evento=evento, participante_documento='DOB-001'
        )
        self.assertEqual(inscripciones.count(), 2)
        self.assertSetEqual(
            set(inscripciones.values_list('categoria_evento_id', flat=True)),
            {categoria_regular.id, categoria_superior.id},
        )
        self.assertEqual(
            AcademiaCompetidora.objects.filter(nombre='Academia Doble').count(), 1
        )

    def test_segunda_inscripcion_no_puede_ser_otra_categoria_regular(self):
        evento, categoria_regular = self.crear_torneo_gratuito()
        otra_regular = CategoriaEvento.objects.create(
            evento=evento, nombre='Otra división regular', edad_minima=18,
        )
        base = {
            'participante_nombre': 'Competidor Regular',
            'participante_documento': 'REG-002',
            'fecha_nacimiento': '1992-02-02',
            'correo': 'regular@example.com',
            'telefono': '3003434343',
            'academia_origen': 'Academia Regular',
            'foto_participante': imagen_prueba('regular-uno.png'),
            'categoria_evento': categoria_regular.id,
            'peso': '73',
            'acepta_reglamento': 'on',
            'acepta_consentimiento': 'on',
            'firma_base64': firma_visible(),
            'logo_academia': imagen_prueba('logo-regular.png'),
        }
        self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]), base
        )
        segundo = base.copy()
        segundo['categoria_evento'] = otra_regular.id
        segundo['foto_participante'] = imagen_prueba('regular-dos.png')
        segundo['firma_base64'] = firma_visible()
        segundo.pop('logo_academia')

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]), segundo
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La segunda inscripción debe ser')
        self.assertEqual(
            InscripcionEvento.objects.filter(
                evento=evento, participante_documento='REG-002'
            ).count(),
            1,
        )
