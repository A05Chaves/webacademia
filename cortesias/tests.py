import base64
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from PIL import Image, ImageDraw

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
        usuario = get_user_model().objects.create_user(
            username='instructor_cortesia',
            password='clave-pruebas',
            first_name='Instructor',
        )
        self.instructor = Instructor.objects.create(
            user=usuario,
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
        self.assertContains(response, 'Selecciona la clase de cortesía')
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
