from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import date, datetime, time, timedelta

from alumnos.models import Alumno
from finanzas.models import CuentaFinanciera, MovimientoFinanciero
from pagos.models import MetodoPagoQR, Pago
from planes.models import Plan, Suscripcion
from clases.models import ClaseProgramada, AsistenciaClase
from instructores.models import Instructor
from config.file_validation import (
    validate_base64_signature,
    validate_image,
    validate_payment_receipt,
)
from gestion.models import SesionTV
import base64


class CronometroLlavesPermisosTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.usuario = self.User.objects.create_user(
            username='usuario_cronometro',
            password='Clave123!',
        )
        self.superusuario = self.User.objects.create_superuser(
            username='admin_llaves',
            password='Clave123!',
            email='admin@example.com',
        )

    def test_usuario_normal_ve_cronometro_sin_modulo_de_llaves(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse('gestion:cronometro_lucha'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="timerTab"')
        self.assertNotContains(response, 'id="bracketTab"')
        self.assertNotContains(response, 'id="bracketPanel"')

    def test_superusuario_ve_llaves_y_tamanos_ampliados(self):
        self.client.force_login(self.superusuario)

        response = self.client.get(reverse('gestion:cronometro_lucha'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="bracketTab"')
        self.assertContains(response, '10 participantes')
        self.assertContains(response, '12 participantes')
        self.assertContains(response, '16 participantes')
        self.assertContains(response, 'BYE')


class ModoTVTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='profesor_tv', password='Clave123!', is_staff=True
        )
        self.otro_staff = get_user_model().objects.create_user(
            username='otro_profesor', password='Clave123!', is_staff=True
        )

    def test_control_crea_sesion_temporal_para_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('gestion:control_tv'))

        self.assertEqual(response.status_code, 200)
        sesion = SesionTV.objects.get(propietario=self.staff)
        self.assertEqual(len(sesion.codigo), 6)
        self.assertContains(response, sesion.codigo)

    def test_tv_se_vincula_por_codigo_y_estado_es_publico(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='123456',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        response = self.client.post(reverse('gestion:vincular_tv'), {'codigo': '123456'})
        self.assertRedirects(response, reverse('gestion:pantalla_tv', args=[sesion.token]))

        estado = self.client.get(reverse('gestion:estado_tv', args=[sesion.token]))
        self.assertEqual(estado.status_code, 200)
        self.assertIn('class', estado.json())
        self.assertEqual(estado.json()['state']['mode'], 'overview')

    def test_solo_propietario_puede_controlar_sesion(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='654321',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.otro_staff)
        response = self.client.post(
            reverse('gestion:accion_tv', args=[sesion.token]),
            {'action': 'red_points', 'delta': '1'},
        )
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('gestion:accion_tv', args=[sesion.token]),
            {'action': 'red_points', 'delta': '1'},
        )
        self.assertEqual(response.status_code, 200)
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado['red_points'], 1)

    def test_inicio_emite_campana_y_reinicio_limpia_marcador(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='111111',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.staff)
        url = reverse('gestion:accion_tv', args=[sesion.token])
        inicio = self.client.post(url, {'action': 'start'})
        self.assertEqual(inicio.json()['state']['sound_event']['type'], 'bell')
        self.client.post(url, {'action': 'pause'})
        self.client.post(url, {'action': 'red_points', 'delta': '1'})
        self.client.post(url, {
            'action': 'names', 'red_name': 'Carlos', 'blue_name': 'Miguel'
        })
        self.client.post(url, {'action': 'reset'})
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado['red_points'], 0)
        self.assertEqual(sesion.estado['red_name'], 'COMPETIDOR ROJO')
        self.assertEqual(sesion.estado['remaining'], 300)

    def test_llave_tv_se_crea_y_avanza_desde_control(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='222222',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.staff)
        url = reverse('gestion:accion_tv', args=[sesion.token])
        response = self.client.post(url, {
            'action': 'bracket_create',
            'size': '4',
            'names': 'ANA\nBEATRIZ\nCARLA',
        })
        self.assertEqual(response.status_code, 200)
        bracket = response.json()['state']['bracket']
        self.assertEqual(bracket['rounds'][0][0]['winner'], 'ANA')
        response = self.client.post(url, {
            'action': 'bracket_winner', 'round': '0', 'match': '1', 'winner': 'BEATRIZ'
        })
        final = response.json()['state']['bracket']['rounds'][1][0]
        self.assertEqual(final['p1'], 'ANA')
        self.assertEqual(final['p2'], 'BEATRIZ')


class CambioNombreUsuarioTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.usuario = self.User.objects.create_user(
            username='documento123',
            password='ClaveTemporal123!',
            debe_cambiar_password=True,
        )
        self.client.force_login(self.usuario)

    def test_primer_acceso_puede_cambiar_usuario_y_password(self):
        response = self.client.post(
            reverse('gestion:cambio_password_obligatorio'),
            {
                'username': 'nuevo_usuario',
                'old_password': 'ClaveTemporal123!',
                'new_password1': 'NuevaClaveSegura456!',
                'new_password2': 'NuevaClaveSegura456!',
            },
        )

        self.assertRedirects(
            response,
            reverse('gestion:horario_clases'),
            fetch_redirect_response=False,
        )
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'nuevo_usuario')
        self.assertTrue(self.usuario.username_modificado)
        self.assertFalse(self.usuario.debe_cambiar_password)
        self.assertTrue(self.usuario.check_password('NuevaClaveSegura456!'))

    def test_rechaza_usuario_duplicado_sin_distinguir_mayusculas(self):
        self.User.objects.create_user(
            username='UsuarioOcupado',
            password='OtraClave123!',
        )

        response = self.client.post(
            reverse('gestion:cambio_password_obligatorio'),
            {
                'username': 'usuarioocupado',
                'old_password': 'ClaveTemporal123!',
                'new_password1': 'NuevaClaveSegura456!',
                'new_password2': 'NuevaClaveSegura456!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este nombre de usuario ya está en uso')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'documento123')
        self.assertTrue(self.usuario.debe_cambiar_password)

    def test_cambio_independiente_solo_se_puede_usar_una_vez(self):
        response = self.client.post(
            reverse('gestion:cambiar_usuario'),
            {
                'username': 'usuario_definitivo',
                'password_actual': 'ClaveTemporal123!',
            },
        )

        self.assertRedirects(
            response,
            reverse('gestion:horario_clases'),
            fetch_redirect_response=False,
        )
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'usuario_definitivo')
        self.assertTrue(self.usuario.username_modificado)

        response = self.client.get(reverse('gestion:cambiar_usuario'))
        self.assertRedirects(
            response,
            reverse('gestion:horario_clases'),
            fetch_redirect_response=False,
        )

    def test_conservar_usuario_en_primer_acceso_no_consume_el_cambio(self):
        response = self.client.post(
            reverse('gestion:cambio_password_obligatorio'),
            {
                'username': 'documento123',
                'old_password': 'ClaveTemporal123!',
                'new_password1': 'NuevaClaveSegura456!',
                'new_password2': 'NuevaClaveSegura456!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.username_modificado)


class SeguridadVistasGestionTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='administrador_pruebas',
            password='clave-segura-pruebas',
            is_staff=True,
        )
        self.client.force_login(self.usuario)

    def test_eliminar_clase_rechaza_get(self):
        response = self.client.get(
            reverse('gestion:eliminar_clase', args=[999999])
        )
        self.assertEqual(response.status_code, 405)

    def test_pagar_pago_programado_rechaza_get(self):
        response = self.client.get(
            reverse('gestion:pagar_pago_programado', args=[999999])
        )
        self.assertEqual(response.status_code, 405)

    def test_aprobar_registro_rechaza_get(self):
        response = self.client.get(
            reverse('gestion:aprobar_registro_legal', args=[999999])
        )
        self.assertEqual(response.status_code, 405)

    def test_ficha_alumno_muestra_usuario_de_acceso(self):
        usuario_alumno = get_user_model().objects.create_user(
            username='usuario_visible_ficha',
            password='clave-alumno-pruebas',
            first_name='Alumno',
            last_name='Visible',
        )
        alumno = Alumno.objects.create(
            user=usuario_alumno,
            documento='DOC-FICHA-1',
        )

        response = self.client.get(
            reverse('gestion:editar_alumno', args=[alumno.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuario de acceso')
        self.assertContains(response, 'usuario_visible_ficha')


class ConfiguracionArchivosTests(TestCase):
    def test_media_esta_configurado(self):
        self.assertEqual(settings.MEDIA_URL, '/media/')
        self.assertEqual(settings.MEDIA_ROOT.name, 'media')


class ValidacionPagoTests(TestCase):
    def setUp(self):
        self.directorio_media = TemporaryDirectory()
        self.configuracion_media = self.settings(
            MEDIA_ROOT=self.directorio_media.name
        )
        self.configuracion_media.enable()
        self.addCleanup(self.configuracion_media.disable)
        self.addCleanup(self.directorio_media.cleanup)

        User = get_user_model()
        self.admin = User.objects.create_user(
            username='admin_pagos',
            password='clave-segura-pruebas',
            is_staff=True,
        )
        self.usuario_alumno = User.objects.create_user(
            username='alumno_pagos',
            password='clave-alumno',
        )
        self.alumno = Alumno.objects.create(
            user=self.usuario_alumno,
            documento='DOC-PRUEBA-1',
            estado=Alumno.Estados.PENDIENTE,
        )
        self.plan = Plan.objects.create(
            nombre='Plan pruebas',
            precio='100000.00',
            duracion_dias=30,
        )
        self.cuenta = CuentaFinanciera.objects.create(
            nombre='Cuenta pruebas',
            tipo=CuentaFinanciera.Tipos.BANCO,
        )
        self.metodo = MetodoPagoQR.objects.create(
            nombre='QR pruebas',
            titular='Academia',
            imagen_qr=SimpleUploadedFile('qr.jpg', b'qr'),
            cuenta_financiera=self.cuenta,
        )
        self.pago = Pago.objects.create(
            alumno=self.alumno,
            plan=self.plan,
            metodo_qr=self.metodo,
            valor='100000.00',
            comprobante=SimpleUploadedFile('comprobante.pdf', b'pago'),
        )
        self.url = reverse('gestion:validar_pago', args=[self.pago.id])
        self.client.force_login(self.admin)

    @patch('gestion.views.send_mail')
    def test_aprobar_pago_crea_suscripcion_y_movimiento(self, enviar_correo):
        response = self.client.post(self.url, {'estado': Pago.Estados.APROBADO})

        self.assertRedirects(response, reverse('gestion:lista_pagos'))
        self.pago.refresh_from_db()
        self.alumno.refresh_from_db()
        self.assertEqual(self.pago.estado, Pago.Estados.APROBADO)
        self.assertEqual(self.pago.validado_por, self.admin)
        self.assertEqual(self.alumno.estado, Alumno.Estados.ACTIVO)
        self.assertTrue(
            Suscripcion.objects.filter(
                alumno=self.alumno,
                plan=self.plan,
                estado=Suscripcion.Estados.ACTIVA,
            ).exists()
        )
        self.assertTrue(
            MovimientoFinanciero.objects.filter(
                pago=self.pago,
                tipo=MovimientoFinanciero.Tipos.INGRESO,
            ).exists()
        )
        enviar_correo.assert_not_called()

    def test_rechazar_pago_no_crea_suscripcion(self):
        response = self.client.post(self.url, {
            'estado': Pago.Estados.RECHAZADO,
            'observacion_admin': 'Comprobante ilegible',
        })

        self.assertRedirects(response, reverse('gestion:lista_pagos'))
        self.pago.refresh_from_db()
        self.assertEqual(self.pago.estado, Pago.Estados.RECHAZADO)
        self.assertFalse(Suscripcion.objects.filter(alumno=self.alumno).exists())
        self.assertFalse(
            MovimientoFinanciero.objects.filter(pago=self.pago).exists()
        )

    @patch(
        'gestion.views.MovimientoFinanciero.objects.get_or_create',
        side_effect=RuntimeError('fallo financiero simulado'),
    )
    def test_error_financiero_revierte_toda_la_aprobacion(self, _movimiento):
        with self.assertRaises(RuntimeError):
            self.client.post(self.url, {'estado': Pago.Estados.APROBADO})

        self.pago.refresh_from_db()
        self.alumno.refresh_from_db()
        self.assertEqual(self.pago.estado, Pago.Estados.PENDIENTE)
        self.assertEqual(self.alumno.estado, Alumno.Estados.PENDIENTE)
        self.assertFalse(Suscripcion.objects.filter(alumno=self.alumno).exists())

    def test_propietario_puede_descargar_su_comprobante(self):
        self.client.force_login(self.usuario_alumno)
        response = self.client.get(
            reverse('serve_media', args=[self.pago.comprobante.name])
        )
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_visitante_no_puede_descargar_comprobante(self):
        self.client.logout()
        response = self.client.get(
            reverse('serve_media', args=[self.pago.comprobante.name])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def test_otro_alumno_no_puede_descargar_comprobante(self):
        otro = get_user_model().objects.create_user(
            username='otro_alumno', password='clave-otro'
        )
        self.client.force_login(otro)
        response = self.client.get(
            reverse('serve_media', args=[self.pago.comprobante.name])
        )
        self.assertEqual(response.status_code, 404)

    def test_qr_de_pago_sigue_siendo_publico(self):
        self.client.logout()
        response = self.client.get(
            reverse('serve_media', args=[self.metodo.imagen_qr.name])
        )
        self.assertEqual(response.status_code, 200)
        response.close()


class ValidadoresArchivosTests(TestCase):
    PNG_VALIDO = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
    )

    def test_acepta_imagen_real(self):
        archivo = SimpleUploadedFile('foto.png', self.PNG_VALIDO)
        validate_image(archivo)

    def test_rechaza_imagen_falsa(self):
        archivo = SimpleUploadedFile('foto.png', b'no es una imagen')
        with self.assertRaises(ValidationError):
            validate_image(archivo)

    def test_acepta_pdf_con_cabecera_valida(self):
        archivo = SimpleUploadedFile('comprobante.pdf', b'%PDF-1.4\n%%EOF')
        validate_payment_receipt(archivo)

    def test_rechaza_pdf_falso(self):
        archivo = SimpleUploadedFile('comprobante.pdf', b'contenido falso')
        with self.assertRaises(ValidationError):
            validate_payment_receipt(archivo)

    def test_rechaza_firma_que_no_es_png(self):
        firma = 'data:image/png;base64,' + base64.b64encode(b'falsa').decode()
        with self.assertRaises(ValidationError):
            validate_base64_signature(firma)


class CalendarioAsistenciaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            username='alumno_calendario', password='clave-alumno'
        )
        self.alumno = Alumno.objects.create(
            user=self.usuario, documento='CAL-001'
        )
        usuario_instructor = User.objects.create_user(
            username='instructor_calendario', password='clave-instructor'
        )
        self.instructor = Instructor.objects.create(
            user=usuario_instructor,
            documento='INS-CAL-001',
            especialidad='Jiu Jitsu',
        )
        self.clase = ClaseProgramada.objects.create(
            dia=ClaseProgramada.DiasSemana.MIERCOLES,
            hora_inicio=time(18, 0),
            hora_fin=time(19, 0),
            disciplina=ClaseProgramada.Disciplinas.JIU_JITSU,
            titulo='Clase técnica',
            instructor=self.instructor,
        )

    def test_visitante_debe_iniciar_sesion(self):
        response = self.client.get(reverse('gestion:mi_asistencia'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def test_confirmacion_home_funciona_con_plan_legacy_sin_flags(self):
        hoy = date(2026, 7, 15)
        plan = Plan.objects.create(
            nombre='Plan legacy confirmación',
            precio='100000',
            duracion_dias=30,
            clases_mes=8,
        )
        Suscripcion.objects.create(
            alumno=self.alumno,
            plan=plan,
            fecha_inicio=hoy - timedelta(days=1),
            fecha_vencimiento=hoy + timedelta(days=29),
            estado=Suscripcion.Estados.ACTIVA,
        )

        momento_clase = timezone.make_aware(datetime(2026, 7, 15, 18, 5))
        with patch('gestion.views.timezone.localtime', return_value=momento_clase):
            response = self.client.post(
                reverse('gestion:confirmar_clase_home'),
                {
                    'clase_id': self.clase.id,
                    'username': 'alumno_calendario',
                    'password': 'clave-alumno',
                },
            )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        self.assertTrue(AsistenciaClase.objects.filter(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=hoy,
            estado=AsistenciaClase.Estados.CONFIRMADA,
        ).exists())

    def test_panel_solo_muestra_asistentes_de_clase_realmente_activa(self):
        siguiente = ClaseProgramada.objects.create(
            dia=ClaseProgramada.DiasSemana.MIERCOLES,
            hora_inicio=time(19, 0),
            hora_fin=time(20, 0),
            disciplina=ClaseProgramada.Disciplinas.JIU_JITSU,
            titulo='Clase siguiente',
            instructor=self.instructor,
        )
        hoy = date(2026, 7, 15)
        asistencia_actual = AsistenciaClase.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=hoy,
            estado=AsistenciaClase.Estados.CONFIRMADA,
        )
        otro_usuario = get_user_model().objects.create_user(
            username='alumno_siguiente', password='clave'
        )
        otro_alumno = Alumno.objects.create(user=otro_usuario, documento='CAL-002')
        AsistenciaClase.objects.create(
            alumno=otro_alumno,
            clase=siguiente,
            fecha_clase=hoy,
            estado=AsistenciaClase.Estados.CONFIRMADA,
        )

        momento = timezone.make_aware(datetime(2026, 7, 15, 18, 45))
        with patch('gestion.views.timezone.localtime', return_value=momento):
            response = self.client.get(reverse('gestion:home_publica'))

        ids = list(response.context['asistencias_hoy'].values_list('id', flat=True))
        self.assertEqual(ids, [asistencia_actual.id])

    def test_formulario_vencido_no_confirma_otra_clase(self):
        momento = timezone.make_aware(datetime(2026, 7, 15, 20, 0))
        with patch('gestion.views.timezone.localtime', return_value=momento):
            response = self.client.post(
                reverse('gestion:confirmar_clase_home'),
                {
                    'clase_id': self.clase.id,
                    'username': 'alumno_calendario',
                    'password': 'clave-alumno',
                },
            )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        self.assertFalse(AsistenciaClase.objects.filter(alumno=self.alumno).exists())

    def test_calendario_solo_marca_asistencias_confirmadas_del_alumno(self):
        AsistenciaClase.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=date(2026, 7, 8),
            estado=AsistenciaClase.Estados.CONFIRMADA,
        )
        AsistenciaClase.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=date(2026, 7, 9),
            estado=AsistenciaClase.Estados.CANCELADA,
        )
        self.client.force_login(self.usuario)

        response = self.client.get(
            reverse('gestion:mi_asistencia'), {'mes': 7, 'anio': 2026}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['dias_asistidos'], 1)
        self.assertEqual(response.context['total_asistencias'], 1)
        dias = [dia for semana in response.context['semanas'] for dia in semana]
        dia_ocho = next(dia for dia in dias if dia['fecha'] == date(2026, 7, 8))
        dia_nueve = next(dia for dia in dias if dia['fecha'] == date(2026, 7, 9))
        self.assertEqual(len(dia_ocho['asistencias']), 1)
        self.assertFalse(dia_nueve['asistencias'])
        self.assertContains(response, 'Clase técnica')

    def test_usuario_sin_perfil_alumno_no_accede_al_calendario(self):
        self.client.force_login(self.instructor.user)
        response = self.client.get(reverse('gestion:mi_asistencia'))
        self.assertEqual(response.status_code, 404)

    def test_marca_inicio_y_fin_sin_inventar_ausencias(self):
        plan = Plan.objects.create(
            nombre='Plan calendario',
            precio='120000',
            duracion_dias=30,
            permite_jiu_jitsu=True,
        )
        Suscripcion.objects.create(
            alumno=self.alumno,
            plan=plan,
            fecha_inicio=date(2026, 6, 1),
            fecha_vencimiento=date(2026, 6, 30),
            estado=Suscripcion.Estados.FINALIZADA,
        )
        AsistenciaClase.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=date(2026, 6, 10),
            estado=AsistenciaClase.Estados.CONFIRMADA,
        )
        self.client.force_login(self.usuario)

        response = self.client.get(
            reverse('gestion:mi_asistencia'), {'mes': 6, 'anio': 2026}
        )

        self.assertEqual(response.status_code, 200)
        dias = [dia for semana in response.context['semanas'] for dia in semana]
        inicio = next(dia for dia in dias if dia['fecha'] == date(2026, 6, 1))
        fin = next(dia for dia in dias if dia['fecha'] == date(2026, 6, 30))
        asistido = next(dia for dia in dias if dia['fecha'] == date(2026, 6, 10))
        dia_sin_registro = next(
            dia for dia in dias if dia['fecha'] == date(2026, 6, 17)
        )
        self.assertTrue(inicio['inicio_mensualidad'])
        self.assertTrue(fin['fin_mensualidad'])
        self.assertTrue(asistido['asistencias'])
        self.assertFalse(dia_sin_registro['asistencias'])
        self.assertFalse(dia_sin_registro['inicio_mensualidad'])
        self.assertFalse(dia_sin_registro['fin_mensualidad'])
        self.assertContains(response, 'Inicio mensualidad')
        self.assertContains(response, 'Fin mensualidad')
        self.assertNotContains(response, 'No asistió')
