from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import date, time

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
import base64


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
