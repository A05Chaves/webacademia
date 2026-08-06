import base64
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageDraw

from alumnos.models import Alumno
from clases.models import ClaseProgramada
from instructores.models import Instructor
from .forms import ClaseCortesiaForm
from .models import ClaseCortesia, ConsentimientoFirmado


def firma_visible():
    image = Image.new('RGB', (200, 100), 'white')
    draw = ImageDraw.Draw(image)
    draw.line((15, 75, 70, 20, 130, 70, 185, 25), fill='black', width=4)
    output = BytesIO()
    image.save(output, format='PNG')
    encoded = base64.b64encode(output.getvalue()).decode()
    return f'data:image/png;base64,{encoded}'


class FlujoCortesiaTests(TestCase):
    def setUp(self):
        self.usuario_instructor = get_user_model().objects.create_user(
            username='instructor_cortesia',
            password='clave-pruebas',
            first_name='Instructor',
        )
        self.instructor = Instructor.objects.create(
            user=self.usuario_instructor,
            documento='INST-CORTESIA',
            especialidad='Jiu Jitsu',
        )
        self.clase_adultos = self.crear_clase(
            'LUNES', '09:00', 'Adultos', ClaseProgramada.PublicosObjetivo.ADULTO
        )
        self.clase_menores = self.crear_clase(
            'MARTES', '10:00', 'Niños', ClaseProgramada.PublicosObjetivo.MENOR
        )
        self.clase_todos = self.crear_clase(
            'MIERCOLES', '11:00', 'Clase familiar', ClaseProgramada.PublicosObjetivo.TODOS
        )

    def crear_clase(self, dia, hora, titulo, publico):
        return ClaseProgramada.objects.create(
            dia=dia,
            hora_inicio=hora,
            hora_fin='12:00',
            disciplina=ClaseProgramada.Disciplinas.JIU_JITSU,
            titulo=titulo,
            publico_objetivo=publico,
            instructor=self.instructor,
        )

    def datos_menor_validos(self):
        return {
            'nombres': 'Participante',
            'apellidos': 'Menor',
            'documento': 'MENOR-001',
            'telefono': '3000000000',
            'correo': 'menor@example.com',
            'edad': 12,
            'tipo_persona': ClaseCortesia.TiposPersona.MENOR,
            'eps': 'EPS pruebas',
            'condicion_medica': 'NINGUNA',
            'nombre_acudiente': 'Acudiente Responsable',
            'documento_acudiente': 'ACU-001',
            'telefono_acudiente': '3110000000',
            'parentesco_acudiente': 'Madre',
            'consentimiento': 'on',
            'firma_base64': firma_visible(),
        }

    def test_horario_de_cortesia_filtra_por_tipo_y_no_muestra_login(self):
        response = self.client.get(
            reverse('gestion:horario_clases'),
            {'cortesia': 'ADULTO'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adultos')
        self.assertContains(response, 'Clase familiar')
        self.assertNotContains(response, 'Niños')
        self.assertContains(response, 'Haz clic en uno de los cuadros de color')
        self.assertNotContains(response, 'Disponible')
        self.assertNotContains(response, 'id="modalAsistencia"')
        self.assertContains(
            response,
            f"{reverse('cortesias:registrar_cortesia', args=[self.clase_adultos.id])}?tipo=ADULTO",
        )

    def test_visitante_no_abre_el_horario_normal_fuera_del_flujo(self):
        response = self.client.get(reverse('gestion:horario_clases'))

        self.assertRedirects(response, reverse('gestion:home_publica'))

    def test_menor_requiere_datos_del_acudiente(self):
        datos = self.datos_menor_validos()
        datos['nombre_acudiente'] = ''
        form = ClaseCortesiaForm(
            data=datos,
            tipo_persona=ClaseCortesia.TiposPersona.MENOR,
            publico_objetivo=ClaseProgramada.PublicosObjetivo.MENOR,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('nombre_acudiente', form.errors)

    def test_edad_debe_corresponder_al_tipo_de_participante(self):
        datos = self.datos_menor_validos()
        datos['edad'] = 19
        form = ClaseCortesiaForm(
            data=datos,
            tipo_persona=ClaseCortesia.TiposPersona.MENOR,
            publico_objetivo=ClaseProgramada.PublicosObjetivo.MENOR,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('edad', form.errors)

    def test_desde_15_ve_clases_de_adultos_pero_requiere_firma_del_acudiente(self):
        datos = self.datos_menor_validos()
        datos.update({
            'edad': 15,
            'tipo_persona': ClaseCortesia.TiposPersona.ADULTO,
        })
        form = ClaseCortesiaForm(
            data=datos,
            tipo_persona=ClaseCortesia.TiposPersona.ADULTO,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_consentimiento_primero_redirige_al_horario_filtrado(self):
        response = self.client.post(
            reverse('cortesias:iniciar_cortesia') + '?tipo=MENOR',
            self.datos_menor_validos(),
        )

        cortesia = ClaseCortesia.objects.get()
        self.assertIsNone(cortesia.clase)
        self.assertRedirects(
            response,
            f"{reverse('gestion:horario_clases')}?cortesia=MENOR&solicitud={cortesia.id}",
        )
        horario = self.client.get(response.url)
        self.assertContains(horario, 'Consentimiento registrado')
        self.assertContains(horario, 'Niños')
        self.assertNotContains(horario, 'Adultos')

    def test_la_edad_corrige_el_grupo_elegido_inicialmente(self):
        datos = self.datos_menor_validos()
        datos['tipo_persona'] = ClaseCortesia.TiposPersona.ADULTO
        response = self.client.post(
            reverse('cortesias:iniciar_cortesia') + '?tipo=ADULTO',
            datos,
        )

        cortesia = ClaseCortesia.objects.get()
        self.assertEqual(cortesia.tipo_persona, ClaseCortesia.TiposPersona.MENOR)
        self.assertIn('cortesia=MENOR', response.url)

    def test_seleccionar_clase_agenda_fecha_y_alerta_al_instructor(self):
        self.client.post(
            reverse('cortesias:iniciar_cortesia') + '?tipo=MENOR',
            self.datos_menor_validos(),
        )
        cortesia = ClaseCortesia.objects.get()
        response = self.client.post(reverse(
            'cortesias:seleccionar_clase_cortesia',
            args=[cortesia.id, self.clase_menores.id],
        ))

        self.assertRedirects(response, reverse('gestion:home_publica'))
        cortesia.refresh_from_db()
        self.assertEqual(cortesia.clase, self.clase_menores)
        self.assertIsNotNone(cortesia.fecha_clase)

        self.client.force_login(self.usuario_instructor)
        lista = self.client.get(reverse('cortesias:lista_cortesias'))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, 'Clases próximas agendadas')
        self.assertContains(lista, 'Niños')

    def crear_cortesia_agendada(self):
        self.client.post(
            reverse('cortesias:iniciar_cortesia') + '?tipo=MENOR',
            self.datos_menor_validos(),
        )
        cortesia = ClaseCortesia.objects.get()
        self.client.post(reverse(
            'cortesias:seleccionar_clase_cortesia',
            args=[cortesia.id, self.clase_menores.id],
        ))
        cortesia.refresh_from_db()
        return cortesia

    def test_instructor_puede_cambiar_contactado_y_asistencia(self):
        cortesia = self.crear_cortesia_agendada()
        self.client.force_login(self.usuario_instructor)

        self.client.post(reverse('cortesias:cambiar_contactado', args=[cortesia.id]))
        self.client.post(reverse('cortesias:cambiar_asistencia', args=[cortesia.id]))
        cortesia.refresh_from_db()

        self.assertTrue(cortesia.contactado)
        self.assertEqual(cortesia.contactado_por, self.usuario_instructor)
        self.assertIsNotNone(cortesia.fecha_contacto)
        self.assertTrue(cortesia.asistio)
        self.assertEqual(cortesia.asistencia_confirmada_por, self.usuario_instructor)

    def test_conversion_muestra_fecha_de_registro_del_estudiante(self):
        cortesia = self.crear_cortesia_agendada()
        alumno_user = get_user_model().objects.create_user(
            username='convertido_cortesia',
            password='clave-pruebas',
            first_name='Participante',
            last_name='Menor',
        )
        alumno = Alumno.objects.create(
            user=alumno_user,
            documento=cortesia.documento,
        )
        self.client.force_login(self.usuario_instructor)

        response = self.client.get(reverse('cortesias:lista_cortesias'))
        cortesia.refresh_from_db()

        self.assertTrue(cortesia.se_convirtio)
        self.assertEqual(cortesia.alumno_convertido, alumno)
        self.assertEqual(cortesia.fecha_conversion, alumno.fecha_registro)
        self.assertContains(response, alumno.fecha_registro.strftime('%Y'))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_campana_envia_solo_a_quien_asistio_y_no_se_convirtio(self):
        cortesia = self.crear_cortesia_agendada()
        cortesia.asistio = True
        cortesia.fecha_clase = timezone.localdate() - timedelta(days=5)
        cortesia.save(update_fields=['asistio', 'fecha_clase'])
        self.client.force_login(self.usuario_instructor)

        response = self.client.post(reverse('cortesias:lista_cortesias'), {
            'activo': 'on',
            'dias_espera': 3,
            'intervalo_dias': 30,
            'maximo_envios': 2,
            'asunto': 'Vuelve a entrenar',
            'mensaje': 'Tenemos una invitación para ti.',
            'accion': 'enviar',
        })

        self.assertRedirects(response, reverse('cortesias:lista_cortesias'))
        cortesia.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [cortesia.correo])
        self.assertEqual(cortesia.cantidad_correos_seguimiento, 1)

    def test_registro_de_menor_guarda_firma_como_acudiente(self):
        url = (
            reverse('cortesias:registrar_cortesia', args=[self.clase_menores.id])
            + '?tipo=MENOR'
        )
        response = self.client.post(url, self.datos_menor_validos())

        self.assertRedirects(response, reverse('gestion:home_publica'))
        cortesia = ClaseCortesia.objects.select_related('consentimiento').get()
        self.assertEqual(cortesia.tipo_persona, ClaseCortesia.TiposPersona.MENOR)
        self.assertEqual(cortesia.consentimiento.nombre_acudiente, 'Acudiente Responsable')
        self.assertIn('firmo este consentimiento en su nombre', cortesia.consentimiento.texto_aceptado)
        self.assertEqual(ConsentimientoFirmado.objects.count(), 1)

    def test_visitante_solo_ve_acciones_publicas_en_home(self):
        response = self.client.get(reverse('gestion:home_publica'))

        self.assertContains(response, 'Regístrate')
        self.assertContains(response, reverse('registro_publico'))
        self.assertContains(response, 'Confirmar clase')
        self.assertContains(response, 'Registrar pago')
        self.assertContains(response, 'Clase de cortesía')
        self.assertContains(response, 'home-action-card')
        self.assertNotContains(response, 'Entrenando ahora')
        self.assertNotContains(response, 'Cronómetro')
        self.assertNotContains(response, 'aria-label="Horario"')
        self.assertNotContains(response, 'aria-label="Registro"')

    def test_visitante_no_puede_abrir_el_cronometro_directamente(self):
        response = self.client.get(reverse('gestion:cronometro_lucha'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('gestion:cronometro_lucha')}",
        )
