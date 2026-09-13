from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from alumnos.models import Alumno


class LoginNormalizadoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='usuarioprueba',
            password='ClaveLogin789!',
        )

    def test_login_quita_espacios_del_usuario(self):
        response = self.client.post(reverse('login'), {
            'username': ' usuario prueba ',
            'password': 'ClaveLogin789!',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            self.usuario.id,
        )

    def test_login_incluye_control_para_ver_contrasena(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, 'id="mostrarPassword"')
        self.assertContains(response, 'fa-eye')
        self.assertContains(response, "replace(/\\s/g, '')", html=False)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RecuperacionPasswordFamiliarTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.primero = Usuario.objects.create_user(
            username='familiar_uno',
            password='clave-familiar-uno',
            email='familia@example.com',
            first_name='Estudiante Uno',
        )
        self.segundo = Usuario.objects.create_user(
            username='familiar_dos',
            password='clave-familiar-dos',
            email='familia@example.com',
            first_name='Estudiante Dos',
        )
        Alumno.objects.create(user=self.primero, documento='DOC-FAM-001')
        Alumno.objects.create(user=self.segundo, documento='DOC-FAM-002')

    def test_formulario_solicita_identificador_y_correo(self):
        response = self.client.get(reverse('password_reset'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuario o documento del estudiante')
        self.assertContains(response, 'correo puede ser compartido')

    def test_documento_selecciona_una_sola_cuenta_del_correo_compartido(self):
        response = self.client.post(reverse('password_reset'), {
            'identificador': 'DOC-FAM-002',
            'email': 'familia@example.com',
        })

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Usuario: familiar_dos', mail.outbox[0].body)
        self.assertNotIn('Usuario: familiar_uno', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['familia@example.com'])
        self.assertIn('https://bjj.lu-a.com/reset/', mail.outbox[0].body)
        self.assertNotIn('testserver', mail.outbox[0].body)
        self.assertNotIn('localhost', mail.outbox[0].body)

    def test_datos_que_no_coinciden_no_envian_y_no_revelan_la_cuenta(self):
        response = self.client.post(reverse('password_reset'), {
            'identificador': 'DOC-INEXISTENTE',
            'email': 'familia@example.com',
        })

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)
