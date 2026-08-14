from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import date, datetime, time, timedelta

from alumnos.models import Alumno
from finanzas.models import CategoriaFinanciera, CuentaFinanciera, MovimientoFinanciero
from pagos.models import (
    CategoriaEvento, Evento, LlaveCategoriaEvento, MetodoPagoQR, Pago,
)
from planes.models import Plan, Suscripcion
from clases.models import ClaseProgramada, AsistenciaClase
from instructores.models import Instructor
from config.file_validation import (
    validate_base64_signature,
    validate_image,
    validate_payment_receipt,
)
from gestion.models import ConfiguracionClases, SesionTV
from gestion.views import limites_confirmacion_clase
from registros_legales.models import RegistroLegalEstudiante
import base64


class FormatoFiltrosFinancierosTests(TestCase):
    def setUp(self):
        administrador = get_user_model().objects.create_user(
            username='admin_formato_anio',
            password='ClaveSegura789!',
            is_staff=True,
        )
        self.client.force_login(administrador)

    def test_anio_financiero_no_recibe_separador_de_miles(self):
        response = self.client.get(
            reverse('gestion:detalle_financiero'),
            {'anio': '2026', 'mes': '8'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026"')
        self.assertNotContains(response, 'value="2.026"')


class RegistroGastoCategoriaTests(TestCase):
    def setUp(self):
        administrador = get_user_model().objects.create_user(
            username='admin_categoria_gasto',
            password='ClaveSegura789!',
            is_staff=True,
        )
        self.client.force_login(administrador)
        self.cuenta = CuentaFinanciera.objects.create(
            nombre='Caja gastos pruebas',
            tipo=CuentaFinanciera.Tipos.EFECTIVO,
            saldo_inicial=500000,
        )

    def test_formulario_muestra_siempre_el_campo_de_categoria_nueva(self):
        response = self.client.get(reverse('gestion:registrar_gasto'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_nueva_categoria"')
        self.assertContains(response, 'Agrega una nueva categoría')
        self.assertNotContains(response, 'id="bloqueNuevaCategoria"')

    def test_crea_categoria_nueva_desde_el_registro_del_gasto(self):
        response = self.client.post(reverse('gestion:registrar_gasto'), {
            'cuenta': self.cuenta.id,
            'categoria': '',
            'nueva_categoria': 'mantenimiento de equipos',
            'evento': '',
            'concepto': 'Reparación de caminadora',
            'valor': '75000',
            'fecha': '2026-08-02T10:30',
            'observaciones': '',
        })

        self.assertRedirects(response, reverse('gestion:dashboard'))
        categoria = CategoriaFinanciera.objects.get(
            nombre='MANTENIMIENTO DE EQUIPOS'
        )
        self.assertEqual(categoria.tipo, CategoriaFinanciera.Tipos.EGRESO)
        self.assertTrue(categoria.activa)
        self.assertTrue(MovimientoFinanciero.objects.filter(
            categoria=categoria,
            concepto='Reparación de caminadora',
            tipo=MovimientoFinanciero.Tipos.EGRESO,
        ).exists())


class RegistrosLegalesFiltroTests(TestCase):
    def setUp(self):
        administrador = get_user_model().objects.create_user(
            username='admin_busqueda_legal', password='clave', is_staff=True
        )
        self.client.force_login(administrador)
        self._crear_registro('María', 'Pérez Gómez', 'DOC-100')
        self._crear_registro('Carlos', 'Ramírez', 'DOC-200')

    def _crear_registro(self, nombres, apellidos, documento):
        return RegistroLegalEstudiante.objects.create(
            tipo_estudiante='ADULTO', nombres=nombres, apellidos=apellidos,
            documento=documento, fecha_nacimiento='2000-01-01',
            direccion='DIRECCIÓN', celular='3000000000',
            usuario_solicitado=f'usuario_{documento}', password_hash='hash',
            fecha_ingreso='2026-08-01', contacto_emergencia_nombre='CONTACTO',
            contacto_emergencia_celular='3000000001', eps='EPS',
            condicion_medica='NINGUNA', texto_consentimiento='CONSENTIMIENTO',
            firma_base64='FIRMA',
        )

    def test_filtra_por_nombre_completo_o_documento(self):
        por_nombre = self.client.get(
            reverse('gestion:lista_registros_legales'), {'q': 'María Pérez'}
        )
        self.assertContains(por_nombre, 'DOC-100')
        self.assertNotContains(por_nombre, 'DOC-200')

        por_documento = self.client.get(
            reverse('gestion:lista_registros_legales'), {'q': 'DOC-200'}
        )
        self.assertContains(por_documento, 'Carlos')
        self.assertNotContains(por_documento, 'DOC-100')


class MiPerfilTests(TestCase):
    def setUp(self):
        self.directorio_media = TemporaryDirectory()
        self.configuracion_media = self.settings(
            MEDIA_ROOT=self.directorio_media.name
        )
        self.configuracion_media.enable()
        self.addCleanup(self.configuracion_media.disable)
        self.addCleanup(self.directorio_media.cleanup)
        self.usuario = get_user_model().objects.create_user(
            username='mi_perfil_usuario', password='clave',
            first_name='Nombre anterior', email='anterior@example.com',
        )
        self.alumno = Alumno.objects.create(
            user=self.usuario, documento='PERFIL-100', direccion='ANTERIOR'
        )
        self.client.force_login(self.usuario)

    def test_usuario_actualiza_solo_sus_datos_editables(self):
        response = self.client.post(reverse('gestion:mi_perfil'), {
            'first_name': 'Andrea',
            'last_name': 'Pérez',
            'email': 'andrea@example.com',
            'telefono': '3001234567',
            'fecha_nacimiento': '2001-05-10',
            'direccion': 'Nueva dirección',
            'nombre_acudiente': '',
            'documento_acudiente': '',
            'parentesco_acudiente': '',
            'telefono_acudiente': '',
        })

        self.assertRedirects(response, reverse('gestion:mi_perfil'))
        self.usuario.refresh_from_db()
        self.alumno.refresh_from_db()
        self.assertEqual(self.usuario.first_name, 'Andrea')
        self.assertEqual(self.usuario.email, 'andrea@example.com')
        self.assertEqual(self.alumno.direccion, 'Nueva dirección')
        self.assertEqual(self.alumno.documento, 'PERFIL-100')

    def test_perfil_no_expone_estado_grado_ni_documento_editables(self):
        response = self.client.get(reverse('gestion:mi_perfil'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PERFIL-100')
        self.assertNotContains(response, 'name="documento"')
        self.assertNotContains(response, 'name="estado"')
        self.assertNotContains(response, 'name="grado"')
        self.assertNotContains(response, 'aria-label="Registro"')

    def test_estudiante_puede_actualizar_su_foto(self):
        foto = SimpleUploadedFile(
            'perfil.png',
            base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
            ),
            content_type='image/png',
        )
        response = self.client.post(reverse('gestion:mi_perfil'), {
            'first_name': 'Andrea',
            'last_name': 'Pérez',
            'email': 'andrea@example.com',
            'telefono': '3001234567',
            'fecha_nacimiento': '2001-05-10',
            'direccion': 'Nueva dirección',
            'nombre_acudiente': '',
            'documento_acudiente': '',
            'parentesco_acudiente': '',
            'telefono_acudiente': '',
            'foto': foto,
        })

        self.assertRedirects(response, reverse('gestion:mi_perfil'))
        self.alumno.refresh_from_db()
        self.assertTrue(self.alumno.foto.name.startswith('alumnos/fotos/'))


class ListaAlumnosFiltroTests(TestCase):
    def setUp(self):
        administrador = get_user_model().objects.create_user(
            username='admin_filtro_alumnos', password='clave', is_staff=True
        )
        angel = get_user_model().objects.create_user(
            username='angel.herrera', password='clave',
            first_name='ANGEL', last_name='HERRERA',
        )
        lucia = get_user_model().objects.create_user(
            username='lucia.egas', password='clave',
            first_name='LUCIA', last_name='EGAS',
        )
        Alumno.objects.create(user=angel, documento='1085000001')
        Alumno.objects.create(user=lucia, documento='1085000002')
        self.client.force_login(administrador)

    def test_busca_por_nombre_completo_y_muestra_nombre_propio(self):
        response = self.client.get(
            reverse('gestion:lista_alumnos'), {'q': 'ANGEL HERRERA'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<td>Angel Herrera</td>', html=True)
        self.assertNotContains(response, '<td>ANGEL HERRERA</td>', html=True)
        self.assertNotContains(response, 'Lucia Egas')

    def test_busca_por_documento(self):
        response = self.client.get(
            reverse('gestion:lista_alumnos'), {'q': '1085000002'}
        )

        self.assertContains(response, 'Lucia Egas')
        self.assertNotContains(response, 'Angel Herrera')


class ConfiguracionYAsistenciaClasesTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin_config_clases', password='clave', is_staff=True
        )
        usuario_instructor = get_user_model().objects.create_user(
            username='instructor_config_clases', password='clave'
        )
        self.instructor = Instructor.objects.create(
            user=usuario_instructor,
            documento='7000000001',
            especialidad='Jiu Jitsu',
        )
        self.clase = ClaseProgramada.objects.create(
            dia=ClaseProgramada.DiasSemana.LUNES,
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
            disciplina=ClaseProgramada.Disciplinas.JIU_JITSU,
            instructor=self.instructor,
            cupo_maximo=20,
        )
        self.client.force_login(self.admin)

    def test_configura_minutos_antes_y_despues(self):
        response = self.client.post(reverse('gestion:configurar_horario'), {
            'minutos_antes_confirmacion': '45',
            'minutos_despues_confirmacion': '25',
        })

        self.assertRedirects(response, reverse('gestion:configurar_horario'))
        configuracion = ConfiguracionClases.cargar()
        self.assertEqual(configuracion.minutos_antes_confirmacion, 45)
        self.assertEqual(configuracion.minutos_despues_confirmacion, 25)

        ahora = timezone.make_aware(datetime(2026, 8, 3, 9, 30))
        inicio, fin = limites_confirmacion_clase(
            self.clase, ahora, configuracion
        )
        self.assertEqual(inicio.time(), time(9, 15))
        self.assertEqual(fin.time(), time(10, 25))

    def test_consulta_asistentes_de_una_fecha_especifica(self):
        usuario_uno = get_user_model().objects.create_user(
            username='asistente_uno', first_name='Laura', last_name='Pérez'
        )
        usuario_dos = get_user_model().objects.create_user(
            username='asistente_dos', first_name='Carlos', last_name='López'
        )
        alumno_uno = Alumno.objects.create(
            user=usuario_uno, documento='8000000001'
        )
        alumno_dos = Alumno.objects.create(
            user=usuario_dos, documento='8000000002'
        )
        AsistenciaClase.objects.create(
            alumno=alumno_uno, clase=self.clase, fecha_clase='2026-08-03'
        )
        AsistenciaClase.objects.create(
            alumno=alumno_dos, clase=self.clase, fecha_clase='2026-07-27'
        )

        response = self.client.get(
            reverse('gestion:asistentes_clase', args=[self.clase.id]),
            {'fecha': '2026-08-03'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Laura Pérez')
        self.assertNotContains(response, 'Carlos López')
        self.assertContains(response, '?fecha=2026-08-03')
        self.assertContains(response, '?fecha=2026-07-27')


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
        self.assertContains(response, 'Editar participantes y distribución')
        self.assertContains(response, 'Separar academias')
        self.assertContains(response, 'function moveParticipant')
        self.assertContains(response, 'function moveParticipantTo')
        self.assertContains(response, 'participant-drag')
        self.assertContains(response, 'Arrastra para cambiar la posición')
        self.assertContains(response, 'fighter-academy')
        self.assertContains(response, 'function renderFighterIdentity')
        self.assertContains(response, 'phaseEndsAt = Date.now()')
        self.assertContains(response, 'countdown = !activeMatch')


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
        self.assertGreater(sesion.expira_en, timezone.now() + timedelta(days=3000))
        self.assertContains(response, sesion.codigo)

    def test_pantalla_tv_ajusta_nombres_largos_del_marcador(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='555555',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        response = self.client.get(
            reverse('gestion:pantalla_tv', args=[sesion.token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'font-size:clamp(22px,3.3vw,52px)')
        self.assertContains(response, 'overflow-wrap:anywhere')
        self.assertContains(response, 'function renderFighterName')
        self.assertContains(response, "teamElement.className='fighter-team'")

    def test_codigo_tv_se_invalida_al_cerrar_sesion(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='987654',
            expira_en=timezone.now() + timedelta(days=3650),
        )
        self.client.force_login(self.staff)
        self.client.logout()

        sesion.refresh_from_db()
        self.assertFalse(sesion.activa)
        response = self.client.post(
            reverse('gestion:vincular_tv'), {'codigo': sesion.codigo}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'venció')

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

    def test_youtube_se_controla_y_se_conserva_al_reiniciar(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='333333',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.staff)
        url = reverse('gestion:accion_tv', args=[sesion.token])

        invalido = self.client.post(url, {
            'action': 'youtube_load', 'value': 'https://example.com/video'
        })
        self.assertEqual(invalido.status_code, 400)

        cargado = self.client.post(url, {
            'action': 'youtube_load',
            'value': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        }).json()['state']
        self.assertEqual(cargado['youtube_video_id'], 'dQw4w9WgXcQ')
        self.assertTrue(cargado['youtube_visible'])
        self.assertEqual(cargado['youtube_command']['type'], 'load')

        volumen = self.client.post(url, {
            'action': 'youtube_volume', 'value': '62'
        }).json()['state']
        self.assertEqual(volumen['youtube_volume'], 62)

        self.client.post(url, {'action': 'reset'})
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado['youtube_video_id'], 'dQw4w9WgXcQ')
        self.assertEqual(sesion.estado['youtube_volume'], 62)

    def test_alistamiento_sonidos_y_reinicio_limpia_marcador(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='111111',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.staff)
        url = reverse('gestion:accion_tv', args=[sesion.token])
        inicio = self.client.post(url, {'action': 'start'})
        self.assertTrue(inicio.json()['state']['preparing'])
        self.assertEqual(inicio.json()['state']['display_remaining'], 5)
        self.assertIsNone(inicio.json()['state']['sound_event'])

        sesion.refresh_from_db()
        sesion.estado['preparation_started_at'] = (
            timezone.now() - timedelta(seconds=6)
        ).isoformat()
        sesion.save(update_fields=['estado'])
        estado_url = reverse('gestion:estado_tv', args=[sesion.token])
        comienzo_round = self.client.get(estado_url).json()['state']
        self.assertTrue(comienzo_round['running'])
        self.assertEqual(comienzo_round['display_remaining'], 300)
        self.assertEqual(comienzo_round['sound_event']['type'], 'bell')

        sesion.refresh_from_db()
        sesion.estado.update({
            'remaining': 11,
            'running': True,
            'started_at': (timezone.now() - timedelta(seconds=1)).isoformat(),
            'warning_done': False,
            'sound_event': None,
        })
        sesion.save(update_fields=['estado'])
        advertencia = self.client.get(estado_url).json()['state']
        self.assertEqual(advertencia['display_remaining'], 10)
        self.assertEqual(advertencia['sound_event']['type'], 'claps')

        sesion.refresh_from_db()
        sesion.estado.update({
            'remaining': 1,
            'running': True,
            'started_at': (timezone.now() - timedelta(seconds=2)).isoformat(),
            'warning_done': True,
            'sound_event': None,
        })
        sesion.save(update_fields=['estado'])
        final = self.client.get(estado_url).json()['state']
        self.assertFalse(final['running'])
        self.assertEqual(final['display_remaining'], 0)
        self.assertEqual(final['sound_event']['type'], 'bell')

        self.client.post(url, {'action': 'pause'})
        self.client.post(url, {'action': 'red_points', 'delta': '1'})
        self.client.post(url, {
            'action': 'names', 'red_name': 'Carlos', 'blue_name': 'Miguel'
        })
        self.client.post(url, {'action': 'duration', 'value': '7'})
        self.client.post(url, {'action': 'reset'})
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado['red_points'], 0)
        self.assertEqual(sesion.estado['red_name'], 'COMPETIDOR ROJO')
        self.assertEqual(sesion.estado['duration'], 420)
        self.assertEqual(sesion.estado['remaining'], 420)

    def test_llave_tv_se_crea_y_avanza_desde_control(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='222222',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.staff)
        url = reverse('gestion:accion_tv', args=[sesion.token])
        self.client.post(url, {'action': 'duration', 'value': '7'})
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

        response = self.client.post(url, {
            'action': 'bracket_load', 'round': '1', 'match': '0'
        })
        state = response.json()['state']
        self.assertEqual(state['mode'], 'timer')
        self.assertEqual(state['duration'], 420)
        self.assertEqual(state['remaining'], 420)
        self.assertEqual(state['red_name'], 'ANA')
        self.assertEqual(state['blue_name'], 'BEATRIZ')
        self.assertIsNotNone(state['active_match'])

        response = self.client.post(url, {
            'action': 'fight_winner', 'side': 'red'
        })
        state = response.json()['state']
        self.assertEqual(state['mode'], 'bracket')
        self.assertEqual(state['bracket']['rounds'][1][0]['winner'], 'ANA')

        response = self.client.post(url, {
            'action': 'bracket_undo', 'round': '0', 'match': '1',
        })
        self.assertEqual(response.status_code, 200)
        final_reopened = response.json()['state']['bracket']['rounds'][1][0]
        self.assertIsNone(final_reopened['p2'])
        self.assertIsNone(final_reopened['winner'])

        response = self.client.post(url, {'action': 'bracket_reset'})
        self.assertIsNone(response.json()['state']['bracket'])

    def test_triangulacion_tv_crea_tres_combates_y_registra_sumision(self):
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='333333',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.staff)
        url = reverse('gestion:accion_tv', args=[sesion.token])
        response = self.client.post(url, {
            'action': 'bracket_create',
            'size': '3',
            'names': 'ANA\nBEATRIZ\nCARLA',
        })
        self.assertEqual(response.status_code, 200)
        bracket = response.json()['state']['bracket']
        self.assertEqual(bracket['type'], 'triangulation')
        self.assertEqual(len(bracket['rounds'][0]), 3)
        self.assertEqual(
            [(match['p1'], match['p2']) for match in bracket['rounds'][0]],
            [('ANA', 'BEATRIZ'), ('BEATRIZ', 'CARLA'), ('CARLA', 'ANA')],
        )

        response = self.client.post(url, {
            'action': 'bracket_winner',
            'round': '0',
            'match': '0',
            'winner': 'ANA',
            'method': 'submission',
            'winner_points': '2',
            'loser_points': '0',
        })
        self.assertEqual(response.status_code, 200)
        match = response.json()['state']['bracket']['rounds'][0][0]
        self.assertEqual(match['winner'], 'ANA')
        self.assertEqual(match['method'], 'submission')
        self.assertEqual(match['winner_points'], 2)
        self.assertIsNone(
            response.json()['state']['bracket']['rounds'][0][1]['winner']
        )

        repeated = self.client.post(url, {
            'action': 'bracket_load', 'round': '0', 'match': '0',
        })
        self.assertEqual(repeated.status_code, 409)

        undone = self.client.post(url, {
            'action': 'bracket_undo', 'round': '0', 'match': '0',
        })
        self.assertEqual(undone.status_code, 200)
        reopened = undone.json()['state']['bracket']['rounds'][0][0]
        self.assertIsNone(reopened['winner'])
        self.assertNotIn('method', reopened)
        self.assertEqual(
            undone.json()['state']['bracket']['rounds'][0][1]['p1'],
            'BEATRIZ',
        )

    def test_superusuario_proyecta_llave_guardada_y_actualiza_resultado(self):
        self.staff.is_superuser = True
        self.staff.save(update_fields=['is_superuser'])
        evento = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Torneo TV',
            descripcion='Torneo para proyectar',
            fecha_inicio=timezone.now() + timedelta(days=1),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
        )
        categoria = CategoriaEvento.objects.create(
            evento=evento, nombre='Adultos livianos'
        )
        llave = LlaveCategoriaEvento.objects.create(
            categoria=categoria,
            actualizada_por=self.staff,
            datos={
                'names': ['ANA', 'BEATRIZ'],
                'configuredSize': 2,
                'capacity': 2,
                'rounds': [[{
                    'p1': 'ANA', 'p2': 'BEATRIZ', 'winner': None,
                }]],
            },
        )
        otra_categoria = CategoriaEvento.objects.create(
            evento=evento, nombre='Adultos pesados'
        )
        LlaveCategoriaEvento.objects.create(
            categoria=otra_categoria,
            actualizada_por=self.staff,
            datos={
                'names': ['CARLOS', 'DANIEL'],
                'configuredSize': 2,
                'capacity': 2,
                'rounds': [[{
                    'p1': 'CARLOS', 'p2': 'DANIEL', 'winner': None,
                }]],
            },
        )
        evento_vencido = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Torneo vencido oculto',
            descripcion='Solo debe quedar en el historial',
            fecha_inicio=timezone.now() - timedelta(days=3),
            fecha_fin=timezone.now() - timedelta(days=2),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
        )
        categoria_vencida = CategoriaEvento.objects.create(
            evento=evento_vencido, nombre='Categoría histórica'
        )
        LlaveCategoriaEvento.objects.create(
            categoria=categoria_vencida,
            actualizada_por=self.staff,
            datos={
                'names': ['HISTÓRICO A', 'HISTÓRICO B'],
                'rounds': [[{
                    'p1': 'HISTÓRICO A', 'p2': 'HISTÓRICO B', 'winner': None,
                }]],
            },
        )
        sesion = SesionTV.objects.create(
            propietario=self.staff,
            codigo='444444',
            expira_en=timezone.now() + timedelta(hours=1),
        )
        self.client.force_login(self.staff)

        control = self.client.get(reverse('gestion:control_tv'))
        self.assertContains(control, 'Proyectar llave guardada del torneo')
        self.assertContains(control, 'Cargar siguiente pelea')
        self.assertContains(control, 'function loadNextTournamentFight')
        self.assertContains(control, 'function previewSavedBracket')
        self.assertContains(control, 'FINALIZADA')
        self.assertContains(control, 'id="bracketParticipantEditor"')
        self.assertContains(control, 'function saveBracketEdit')
        self.assertContains(control, 'Editar participantes de la llave cargada')
        self.assertContains(control, 'id="savedBracketEvent"')
        self.assertContains(control, 'Categoría / llave')
        self.assertContains(control, 'Torneo TV')
        self.assertNotContains(control, 'Torneo vencido oculto')
        cronometro = self.client.get(reverse('gestion:cronometro_lucha'))
        self.assertContains(cronometro, 'Torneo TV')
        self.assertNotContains(cronometro, 'Torneo vencido oculto')
        url = reverse('gestion:accion_tv', args=[sesion.token])
        vista_previa = self.client.post(url, {
            'action': 'bracket_import',
            'category': categoria.id,
            'preview': '1',
        })
        self.assertEqual(vista_previa.status_code, 200)
        self.assertNotEqual(vista_previa.json()['state']['mode'], 'bracket')
        self.assertEqual(
            vista_previa.json()['state']['bracket_source_category_id'],
            categoria.id,
        )

        importada = self.client.post(url, {
            'action': 'bracket_import', 'category': categoria.id,
        })
        self.assertEqual(importada.status_code, 200)
        state = importada.json()['state']
        self.assertEqual(state['mode'], 'bracket')
        self.assertEqual(state['bracket_source_category_id'], categoria.id)
        self.assertEqual(state['bracket']['rounds'][0][0]['p1'], 'ANA')

        vencida = self.client.post(url, {
            'action': 'bracket_import', 'category': categoria_vencida.id,
        })
        self.assertEqual(vencida.status_code, 404)

        combate = self.client.post(url, {
            'action': 'bracket_load', 'round': '0', 'match': '0',
        })
        self.assertEqual(combate.status_code, 200)
        self.assertEqual(
            combate.json()['state']['active_match']['round_name'],
            'FINAL',
        )
        self.assertEqual(
            combate.json()['state']['next_fight']['category_id'],
            otra_categoria.id,
        )
        self.assertEqual(combate.json()['state']['next_fight']['p1'], 'CARLOS')

        inicio = self.client.post(url, {'action': 'start'})
        self.assertEqual(inicio.status_code, 200)
        self.assertTrue(inicio.json()['state']['running'])
        self.assertFalse(inicio.json()['state']['preparing'])
        self.assertEqual(inicio.json()['state']['sound_event']['type'], 'bell')

        ganador = self.client.post(url, {
            'action': 'bracket_winner',
            'round': '0',
            'match': '0',
            'winner': 'ANA',
        })
        self.assertEqual(ganador.status_code, 200)
        llave.refresh_from_db()
        self.assertEqual(llave.datos['rounds'][0][0]['winner'], 'ANA')

        recarga_finalizada = self.client.post(url, {
            'action': 'bracket_load', 'round': '0', 'match': '0',
        })
        self.assertEqual(recarga_finalizada.status_code, 409)
        cambio_finalizada = self.client.post(url, {
            'action': 'bracket_winner',
            'round': '0',
            'match': '0',
            'winner': 'BEATRIZ',
        })
        self.assertEqual(cambio_finalizada.status_code, 409)

        deshecho = self.client.post(url, {
            'action': 'bracket_undo', 'round': '0', 'match': '0',
        })
        self.assertEqual(deshecho.status_code, 200)
        llave.refresh_from_db()
        self.assertIsNone(llave.datos['rounds'][0][0]['winner'])

        editada = self.client.post(url, {
            'action': 'bracket_create',
            'size': '4',
            'names': 'ANA\nBEATRIZ CORREGIDA\nDANIEL\nELENA',
            'preserve_source': '1',
        })
        self.assertEqual(editada.status_code, 200)
        self.assertEqual(
            editada.json()['state']['bracket_source_category_id'],
            categoria.id,
        )
        llave.refresh_from_db()
        self.assertIn('BEATRIZ CORREGIDA', llave.datos['names'])
        self.assertTrue(all(
            not match.get('winner')
            for round_matches in llave.datos['rounds']
            for match in round_matches
            if '__BYE__' not in {match.get('p1'), match.get('p2')}
        ))


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

    def test_administrador_habilita_asistencia_vencida_desde_ficha(self):
        usuario_alumno = get_user_model().objects.create_user(
            username='alumno_permiso_vencido',
            password='clave-alumno-pruebas',
            first_name='Alumno',
            last_name='Autorizado',
        )
        alumno = Alumno.objects.create(
            user=usuario_alumno,
            documento='DOC-PERMISO-VENCIDO',
            estado=Alumno.Estados.VENCIDO,
        )

        response = self.client.post(
            reverse('gestion:editar_alumno', args=[alumno.id]),
            {
                'first_name': 'Alumno',
                'last_name': 'Autorizado',
                'email': '',
                'telefono': '',
                'documento': alumno.documento,
                'fecha_nacimiento': '',
                'direccion': '',
                'disciplina': Alumno.Disciplinas.JIU_JITSU_BRASILERO,
                'grado': '',
                'nombre_acudiente': '',
                'documento_acudiente': '',
                'parentesco_acudiente': '',
                'telefono_acudiente': '',
                'estado': Alumno.Estados.VENCIDO,
                'permitir_asistencia_vencida': 'on',
            },
        )

        self.assertRedirects(response, reverse('gestion:lista_alumnos'))
        alumno.refresh_from_db()
        self.assertTrue(alumno.permitir_asistencia_vencida)


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


class ListaSuscripcionesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username='admin_suscripciones',
            password='clave',
            is_staff=True,
        )
        usuario_activo = User.objects.create_user(
            username='laura.activa',
            first_name='Laura',
            last_name='Activa',
            password='clave',
        )
        usuario_vencido = User.objects.create_user(
            username='carlos.vencido',
            first_name='Carlos',
            last_name='Vencido',
            password='clave',
        )
        self.alumno_activo = Alumno.objects.create(
            user=usuario_activo, documento='ACT-100'
        )
        self.alumno_vencido = Alumno.objects.create(
            user=usuario_vencido, documento='VEN-200'
        )
        self.plan = Plan.objects.create(
            nombre='Plan mensual',
            precio=100000,
            duracion_dias=30,
        )
        hoy = timezone.localdate()
        Suscripcion.objects.create(
            alumno=self.alumno_activo,
            plan=self.plan,
            fecha_inicio=hoy - timedelta(days=5),
            fecha_vencimiento=hoy + timedelta(days=24),
            estado=Suscripcion.Estados.ACTIVA,
        )
        Suscripcion.objects.create(
            alumno=self.alumno_vencido,
            plan=self.plan,
            fecha_inicio=hoy - timedelta(days=60),
            fecha_vencimiento=hoy - timedelta(days=31),
            estado=Suscripcion.Estados.VENCIDA,
        )
        cuenta = CuentaFinanciera.objects.create(
            nombre='Cuenta suscripciones',
            tipo=CuentaFinanciera.Tipos.BANCO,
        )
        metodo = MetodoPagoQR.objects.create(
            nombre='QR suscripciones',
            titular='Academia',
            imagen_qr=SimpleUploadedFile('qr-sus.png', b'qr'),
            cuenta_financiera=cuenta,
        )
        for referencia in ('M-1', 'M-2'):
            Pago.objects.create(
                alumno=self.alumno_activo,
                plan=self.plan,
                metodo_qr=metodo,
                tipo=Pago.Tipos.MENSUALIDAD,
                estado=Pago.Estados.APROBADO,
                valor=100000,
                referencia_pago=referencia,
                comprobante=SimpleUploadedFile(
                    f'{referencia}.pdf', b'%PDF-1.4'
                ),
            )
        self.client.force_login(self.admin)

    def test_por_defecto_solo_muestra_suscripciones_activas(self):
        response = self.client.get(reverse('gestion:lista_suscripciones'))

        self.assertContains(response, 'Laura Activa')
        self.assertNotContains(response, 'Carlos Vencido')
        self.assertEqual(
            response.context['suscripciones'][0].mensualidades_pagadas, 2
        )

    def test_filtro_vencidas_y_busqueda_por_documento(self):
        vencidas = self.client.get(
            reverse('gestion:lista_suscripciones'),
            {'estado': 'vencidas'},
        )
        self.assertContains(vencidas, 'Carlos Vencido')
        self.assertNotContains(vencidas, 'Laura Activa')

        busqueda = self.client.get(
            reverse('gestion:lista_suscripciones'),
            {'q': 'VEN-200'},
        )
        self.assertContains(busqueda, 'Carlos Vencido')
        self.assertEqual(busqueda.context['estado_filtro'], 'todas')


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

    def test_administrador_puede_ver_calendario_del_estudiante(self):
        administrador = get_user_model().objects.create_user(
            username='admin_calendario',
            password='clave-admin',
            is_staff=True,
        )
        AsistenciaClase.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=date(2026, 7, 8),
            estado=AsistenciaClase.Estados.CONFIRMADA,
        )
        self.client.force_login(administrador)

        response = self.client.get(
            reverse('gestion:asistencia_alumno', args=[self.alumno.id]),
            {'mes': 7, 'anio': 2026},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['vista_administrativa'])
        self.assertContains(response, f'Asistencia de {self.alumno}')
        self.assertContains(response, 'Clase técnica')

    def test_estudiante_no_puede_ver_calendario_de_otro(self):
        otro_usuario = get_user_model().objects.create_user(
            username='otro_calendario', password='clave'
        )
        otro = Alumno.objects.create(
            user=otro_usuario, documento='CAL-OTRO'
        )
        self.client.force_login(self.usuario)

        response = self.client.get(
            reverse('gestion:asistencia_alumno', args=[otro.id])
        )

        self.assertEqual(response.status_code, 403)

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

    def test_estudiante_con_sesion_confirma_sin_credenciales_y_conserva_sesion(self):
        hoy = date(2026, 7, 15)
        plan = Plan.objects.create(
            nombre='Plan confirmación rápida',
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
        self.client.force_login(self.usuario)
        momento_clase = timezone.make_aware(datetime(2026, 7, 15, 18, 5))

        with patch('gestion.views.timezone.localtime', return_value=momento_clase):
            response = self.client.post(
                reverse('gestion:confirmar_clase_home'),
                {'clase_id': self.clase.id},
                follow=True,
            )

        self.assertTrue(AsistenciaClase.objects.filter(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=hoy,
        ).exists())
        self.assertIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'data-clase-feedback')
        self.assertContains(response, 'Clase confirmada')
        self.assertContains(response, 'data-voz="Clase confirmada"')
        self.assertContains(response, 'fa-circle-check')

    def test_error_de_confirmacion_muestra_alerta_grande_con_x_roja(self):
        self.client.force_login(self.usuario)
        momento_clase = timezone.make_aware(datetime(2026, 7, 15, 18, 5))

        with patch('gestion.views.timezone.localtime', return_value=momento_clase):
            response = self.client.post(
                reverse('gestion:confirmar_clase_home'),
                {'clase_id': self.clase.id},
                follow=True,
            )

        self.assertContains(response, 'No se confirmó la clase')
        self.assertContains(response, 'fa-circle-xmark')
        self.assertContains(response, 'No tienes un plan iniciado')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_mensualidad_vencida_confirma_muestra_dias_y_avisa_administradores(self):
        plan = Plan.objects.create(
            nombre='Plan vencido con acceso',
            precio='100000',
            duracion_dias=30,
            clases_mes=8,
        )
        Suscripcion.objects.create(
            alumno=self.alumno,
            plan=plan,
            fecha_inicio=date(2026, 6, 11),
            fecha_vencimiento=date(2026, 7, 10),
            estado=Suscripcion.Estados.VENCIDA,
        )
        self.alumno.estado = Alumno.Estados.VENCIDO
        self.alumno.permitir_asistencia_vencida = True
        self.alumno.save(update_fields=['estado', 'permitir_asistencia_vencida'])
        get_user_model().objects.create_user(
            username='admin_alerta_vencido',
            password='clave-admin',
            email='admin-alertas@galeras.test',
            is_staff=True,
        )
        self.client.force_login(self.usuario)
        momento = timezone.make_aware(datetime(2026, 7, 15, 18, 5))

        with patch('gestion.views.timezone.localtime', return_value=momento):
            response = self.client.post(
                reverse('gestion:confirmar_clase_home'),
                {'clase_id': self.clase.id},
                follow=True,
            )

        self.assertTrue(AsistenciaClase.objects.filter(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=date(2026, 7, 15),
        ).exists())
        self.assertContains(response, 'mensualidad está vencida hace 5 día(s)')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin-alertas@galeras.test'])
        self.assertIn('5 día(s) de vencimiento', mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_mensualidad_vencida_bloquea_por_defecto(self):
        plan = Plan.objects.create(
            nombre='Plan vencido sin permiso',
            precio='100000',
            duracion_dias=30,
            clases_mes=8,
        )
        Suscripcion.objects.create(
            alumno=self.alumno,
            plan=plan,
            fecha_inicio=date(2026, 6, 11),
            fecha_vencimiento=date(2026, 7, 10),
            estado=Suscripcion.Estados.VENCIDA,
        )
        self.alumno.estado = Alumno.Estados.VENCIDO
        self.alumno.save(update_fields=['estado'])
        self.client.force_login(self.usuario)
        momento = timezone.make_aware(datetime(2026, 7, 15, 18, 5))

        with patch('gestion.views.timezone.localtime', return_value=momento):
            response = self.client.post(
                reverse('gestion:confirmar_clase_home'),
                {'clase_id': self.clase.id},
                follow=True,
            )

        self.assertFalse(AsistenciaClase.objects.filter(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=date(2026, 7, 15),
        ).exists())
        self.assertContains(response, 'mensualidad está vencida hace 5 día(s)')
        self.assertContains(response, 'No tienes autorización')
        self.assertEqual(len(mail.outbox), 0)

    def test_estudiante_suspendido_no_puede_confirmar_aunque_tenga_plan(self):
        plan = Plan.objects.create(
            nombre='Plan suspendido', precio='100000', duracion_dias=30,
        )
        Suscripcion.objects.create(
            alumno=self.alumno,
            plan=plan,
            fecha_inicio=date(2026, 7, 1),
            fecha_vencimiento=date(2026, 7, 30),
            estado=Suscripcion.Estados.ACTIVA,
        )
        self.alumno.estado = Alumno.Estados.SUSPENDIDO
        self.alumno.save(update_fields=['estado'])
        self.client.force_login(self.usuario)
        momento = timezone.make_aware(datetime(2026, 7, 15, 18, 5))

        with patch('gestion.views.timezone.localtime', return_value=momento):
            response = self.client.post(
                reverse('gestion:confirmar_clase_home'),
                {'clase_id': self.clase.id},
                follow=True,
            )

        self.assertFalse(AsistenciaClase.objects.filter(alumno=self.alumno).exists())
        self.assertContains(response, 'acceso está suspendido')

    def test_lista_home_se_actualiza_y_muestra_confirmados_antes_de_iniciar(self):
        confirmacion = timezone.make_aware(datetime(2026, 7, 15, 17, 38))
        AsistenciaClase.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=date(2026, 7, 15),
            estado=AsistenciaClase.Estados.CONFIRMADA,
            fecha_confirmacion=confirmacion,
        )
        self.client.force_login(self.usuario)
        antes_de_iniciar = timezone.make_aware(datetime(2026, 7, 15, 17, 40))

        with patch('gestion.views.timezone.localtime', return_value=antes_de_iniciar):
            response = self.client.get(reverse('gestion:asistencias_home_actuales'))
            pagina = self.client.get(reverse('gestion:home_publica'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['asistencias'][0]['nombre'], str(self.alumno))
        self.assertContains(pagina, str(self.alumno))
        self.assertContains(pagina, 'actualizarAsistenciasHome')
        self.assertContains(pagina, '3000')

    def test_horario_reconoce_sesion_del_estudiante_para_confirmacion_rapida(self):
        self.usuario.debe_cambiar_password = False
        self.usuario.save(update_fields=['debe_cambiar_password'])
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('gestion:horario_clases'))

        self.assertContains(response, 'Confirmarás clase como')
        self.assertContains(response, 'próximas confirmaciones', count=0)

    def test_panel_mantiene_clase_actual_aunque_la_siguiente_ya_se_pueda_confirmar(self):
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
        asistencia_siguiente = AsistenciaClase.objects.create(
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
        self.assertNotIn(asistencia_siguiente.id, ids)

    def test_usuario_elige_clase_cuando_se_cruzan_ventanas_de_confirmacion(self):
        siguiente = ClaseProgramada.objects.create(
            dia=ClaseProgramada.DiasSemana.MIERCOLES,
            hora_inicio=time(19, 0),
            hora_fin=time(20, 0),
            disciplina=ClaseProgramada.Disciplinas.JIU_JITSU,
            titulo='Clase siguiente',
            instructor=self.instructor,
        )
        configuracion = ConfiguracionClases.cargar()
        configuracion.minutos_antes_confirmacion = 30
        configuracion.minutos_despues_confirmacion = 60
        configuracion.save()
        hoy = date(2026, 7, 15)
        plan = Plan.objects.create(
            nombre='Plan seleccion de clase',
            precio='100000',
            duracion_dias=30,
            clases_mes=8,
        )
        Suscripcion.objects.create(
            alumno=self.alumno,
            plan=plan,
            fecha_inicio=hoy - timedelta(days=1),
            fecha_vencimiento=hoy + timedelta(days=28),
            estado=Suscripcion.Estados.ACTIVA,
        )
        self.client.force_login(self.usuario)
        cruce = timezone.make_aware(datetime(2026, 7, 15, 18, 45))

        with patch('gestion.views.timezone.localtime', return_value=cruce):
            pagina = self.client.get(reverse('gestion:home_publica'))
            respuesta = self.client.post(
                reverse('gestion:confirmar_clase_home'),
                {'clase_id': siguiente.id},
            )
            panel_actual = self.client.get(
                reverse('gestion:asistencias_home_actuales')
            )

        self.assertEqual(
            [clase.id for clase in pagina.context['clases_confirmables']],
            [self.clase.id, siguiente.id],
        )
        self.assertContains(pagina, 'Selecciona la clase a la que vas a ingresar')
        self.assertContains(pagina, 'name="clase_id"', count=2)
        self.assertRedirects(respuesta, reverse('gestion:home_publica'))
        self.assertTrue(AsistenciaClase.objects.filter(
            alumno=self.alumno,
            clase=siguiente,
            fecha_clase=hoy,
        ).exists())
        self.assertEqual(panel_actual.json()['clase']['nombre'], 'Clase técnica')
        self.assertEqual(panel_actual.json()['asistencias'], [])

        inicio_siguiente = timezone.make_aware(datetime(2026, 7, 15, 19, 0))
        with patch('gestion.views.timezone.localtime', return_value=inicio_siguiente):
            panel_siguiente = self.client.get(
                reverse('gestion:asistencias_home_actuales')
            )
        self.assertEqual(panel_siguiente.json()['clase']['nombre'], 'Clase siguiente')
        self.assertEqual(
            panel_siguiente.json()['asistencias'][0]['nombre'],
            str(self.alumno),
        )

    def test_profesor_confirma_sin_plan_ni_restriccion_horaria(self):
        usuario_profesor = self.instructor.user
        self.client.force_login(usuario_profesor)
        fuera_de_ventana = timezone.make_aware(
            datetime(2026, 7, 15, 10, 0)
        )

        with patch(
            'gestion.views.timezone.localtime',
            return_value=fuera_de_ventana,
        ):
            pagina = self.client.get(reverse('gestion:home_publica'))
            respuesta = self.client.post(
                reverse('gestion:confirmar_clase_home'),
                {'clase_id': self.clase.id},
            )

        self.assertEqual(
            [clase.id for clase in pagina.context['clases_confirmables']],
            [self.clase.id],
        )
        self.assertRedirects(respuesta, reverse('gestion:home_publica'))
        asistencia = AsistenciaClase.objects.get(
            instructor=self.instructor,
            clase=self.clase,
            fecha_clase=date(2026, 7, 15),
        )
        self.assertIsNone(asistencia.alumno)
        self.assertEqual(asistencia.tipo_participante, 'Profesor')

        durante_clase = timezone.make_aware(datetime(2026, 7, 15, 18, 5))
        with patch('gestion.views.timezone.localtime', return_value=durante_clase):
            panel = self.client.get(reverse('gestion:asistencias_home_actuales'))
        self.assertEqual(panel.json()['asistencias'][0]['nombre'], str(self.instructor))
        self.assertEqual(panel.json()['asistencias'][0]['tipo'], 'Profesor')

    def test_administrador_convierte_estudiante_en_profesor_sin_borrar_historial(self):
        administrador = get_user_model().objects.create_user(
            username='admin-cambio-perfil',
            password='clave-admin',
            is_staff=True,
        )
        asistencia = AsistenciaClase.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            fecha_clase=date(2026, 7, 8),
        )
        self.client.force_login(administrador)

        respuesta = self.client.post(
            reverse('gestion:editar_alumno', args=[self.alumno.id]),
            {
                'first_name': 'Profesor',
                'last_name': 'Promovido',
                'email': 'profesor@example.com',
                'telefono': '3001234567',
                'documento': self.alumno.documento,
                'fecha_nacimiento': '',
                'direccion': '',
                'disciplina': self.alumno.disciplina,
                'grado': '',
                'nombre_acudiente': '',
                'documento_acudiente': '',
                'parentesco_acudiente': '',
                'telefono_acudiente': '',
                'estado': self.alumno.estado,
                'rol': 'INSTRUCTOR',
                'especialidad': 'Jiu Jitsu',
                'instructor_activo': 'on',
            },
        )

        self.assertRedirects(respuesta, reverse('gestion:lista_alumnos'))
        self.usuario.refresh_from_db()
        self.alumno.refresh_from_db()
        profesor = Instructor.objects.get(user=self.usuario)
        self.assertEqual(self.usuario.rol, 'INSTRUCTOR')
        self.assertTrue(profesor.activo)
        self.assertEqual(profesor.documento, self.alumno.documento)
        self.assertTrue(Alumno.objects.filter(pk=self.alumno.pk).exists())
        self.assertTrue(AsistenciaClase.objects.filter(pk=asistencia.pk).exists())

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
