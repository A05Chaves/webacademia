import base64
from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from PIL import Image, ImageDraw

from planes.models import Plan
from alumnos.models import Alumno
from instructores.models import Instructor
from .forms import RegistroLegalEstudianteForm
from .models import RegistroLegalEstudiante


def imagen_png(con_firma=False):
    image = Image.new('RGB', (200, 100), 'white')
    if con_firma:
        draw = ImageDraw.Draw(image)
        draw.line((20, 70, 80, 25, 150, 65, 180, 30), fill='black', width=4)
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


class RegistroLegalObligatorioTests(TestCase):
    def setUp(self):
        self.directorio_media = TemporaryDirectory()
        self.configuracion_media = self.settings(
            MEDIA_ROOT=self.directorio_media.name
        )
        self.configuracion_media.enable()
        self.addCleanup(self.configuracion_media.disable)
        self.addCleanup(self.directorio_media.cleanup)
        self.plan = Plan.objects.create(
            nombre='Plan registro', precio='90000', duracion_dias=30
        )

    def datos_validos(self):
        firma = base64.b64encode(imagen_png(con_firma=True)).decode()
        return {
            'tipo_estudiante': 'ADULTO',
            'nombres': 'Estudiante',
            'apellidos': 'Prueba',
            'documento': 'REG-001',
            'fecha_nacimiento': '2000-01-01',
            'direccion': 'Dirección de prueba',
            'celular': '3000000001',
            'correo': 'registro@example.com',
            'fecha_ingreso': '2026-07-12',
            'plan_interes': self.plan.id,
            'contacto_emergencia_nombre': 'Contacto Prueba',
            'contacto_emergencia_celular': '3000000002',
            'eps': 'EPS prueba',
            'condicion_medica': 'NINGUNA',
            'acepta_reglamento': 'on',
            'acepta_riesgos': 'on',
            'autoriza_imagen': 'on',
            'firma_base64': f'data:image/png;base64,{firma}',
        }

    def foto_valida(self):
        return SimpleUploadedFile(
            'foto.png', imagen_png(), content_type='image/png'
        )

    def test_campos_generales_estan_marcados_como_obligatorios(self):
        form = RegistroLegalEstudianteForm()
        opcionales_para_adulto = {
            'nombre_acudiente', 'documento_acudiente',
            'parentesco_acudiente', 'celular_acudiente',
        }
        for name, field in form.fields.items():
            if name not in opcionales_para_adulto:
                self.assertTrue(field.required, name)

    def test_no_guarda_registro_sin_firma(self):
        data = self.datos_validos()
        data['firma_base64'] = ''
        response = self.client.post(
            reverse('registro_publico'), data, files={'foto': self.foto_valida()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Debe realizar la firma')
        self.assertEqual(RegistroLegalEstudiante.objects.count(), 0)

    def test_no_acepta_imagen_blanca_como_firma(self):
        data = self.datos_validos()
        firma_blanca = base64.b64encode(imagen_png()).decode()
        data['firma_base64'] = f'data:image/png;base64,{firma_blanca}'
        form = RegistroLegalEstudianteForm(
            data=data, files={'foto': self.foto_valida()}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('firma_base64', form.errors)

    def test_formulario_completo_si_es_valido(self):
        form = RegistroLegalEstudianteForm(
            data=self.datos_validos(), files={'foto': self.foto_valida()}
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_administrador_no_aprueba_registro_automaticamente(self):
        administrador = get_user_model().objects.create_user(
            username='admin_registro',
            password='clave-segura-pruebas',
            is_staff=True,
        )
        self.client.force_login(administrador)
        data = self.datos_validos()
        data['foto'] = self.foto_valida()

        response = self.client.post(reverse('registro_publico'), data)

        self.assertRedirects(response, reverse('registro_exitoso'))
        registro = RegistroLegalEstudiante.objects.get(documento='REG-001')
        self.assertEqual(
            registro.estado,
            RegistroLegalEstudiante.Estados.PENDIENTE_VALIDACION,
        )
        self.assertFalse(Alumno.objects.filter(documento='REG-001').exists())

    def test_datos_repetidos_no_crean_un_segundo_registro(self):
        primer_envio = self.datos_validos()
        primer_envio['foto'] = self.foto_valida()
        response = self.client.post(reverse('registro_publico'), primer_envio)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RegistroLegalEstudiante.objects.count(), 1)

        segundo_envio = self.datos_validos()
        segundo_envio['foto'] = self.foto_valida()
        response = self.client.post(reverse('registro_publico'), segundo_envio)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe un estudiante o registro')
        self.assertContains(response, 'Ya existe un registro con este correo')
        self.assertContains(response, 'Ya existe un registro con este celular')
        self.assertEqual(RegistroLegalEstudiante.objects.count(), 1)

    def test_validacion_intermedia_detecta_datos_existentes(self):
        data = self.datos_validos()
        data['foto'] = self.foto_valida()
        self.client.post(reverse('registro_publico'), data)

        response = self.client.post(reverse('validar_datos_registro'), {
            'documento': 'REG-001',
            'correo': 'REGISTRO@example.com',
            'celular': '3000000001',
        })

        self.assertEqual(response.status_code, 200)
        resultado = response.json()
        self.assertFalse(resultado['valido'])
        self.assertEqual(
            set(resultado['errores']), {'documento', 'correo', 'celular'}
        )

    def test_documento_de_instructor_no_puede_registrarse_como_estudiante(self):
        usuario_instructor = get_user_model().objects.create_user(
            username='cuenta_instructor', password='clave-instructor'
        )
        Instructor.objects.create(
            user=usuario_instructor,
            documento='DOC-INSTRUCTOR-1',
            especialidad='Jiu Jitsu',
        )

        response = self.client.post(reverse('validar_datos_registro'), {
            'documento': 'DOC-INSTRUCTOR-1',
            'correo': 'nuevo@example.com',
            'celular': '3110000000',
        })
        self.assertFalse(response.json()['valido'])
        self.assertIn('documento', response.json()['errores'])

        data = self.datos_validos()
        data['documento'] = 'DOC-INSTRUCTOR-1'
        form = RegistroLegalEstudianteForm(
            data=data, files={'foto': self.foto_valida()}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('documento', form.errors)
        self.assertEqual(RegistroLegalEstudiante.objects.count(), 0)
