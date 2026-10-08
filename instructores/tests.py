from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno

from .models import Instructor, SolicitudRegistroProfesor


class RegistroYAdministracionProfesoresTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.admin = self.User.objects.create_user(
            username='administrador_pruebas',
            password='ClaveAdmin123!',
            rol=self.User.Roles.ADMIN,
            is_staff=True,
        )

    def datos_solicitud(self):
        return {
            'nombres': 'Carlos',
            'apellidos': 'Profesor',
            'documento': '1.234.567',
            'celular': '3001234567',
            'correo': 'carlos.profesor@example.com',
            'especialidad': 'Jiu Jitsu',
            'usuario_solicitado': 'carlos_profesor',
            'password1': 'ClaveSegura123!',
            'password2': 'ClaveSegura123!',
        }

    def test_registro_publico_crea_solicitud_pendiente_sin_crear_usuario(self):
        response = self.client.post(
            reverse('instructores:registro_profesor'),
            self.datos_solicitud(),
        )

        self.assertRedirects(
            response, reverse('instructores:registro_profesor_exitoso')
        )
        solicitud = SolicitudRegistroProfesor.objects.get()
        self.assertEqual(solicitud.documento, '1234567')
        self.assertEqual(solicitud.estado, SolicitudRegistroProfesor.Estados.PENDIENTE)
        self.assertTrue(check_password('ClaveSegura123!', solicitud.password_hash))
        self.assertFalse(
            self.User.objects.filter(username='carlos_profesor').exists()
        )

    def test_aprobar_solicitud_crea_profesor_sin_permisos_administrativos(self):
        self.client.post(
            reverse('instructores:registro_profesor'),
            self.datos_solicitud(),
        )
        solicitud = SolicitudRegistroProfesor.objects.get()
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:aprobar_solicitud_profesor', args=[solicitud.id])
        )

        self.assertRedirects(response, reverse('gestion:configurar_perfiles'))
        usuario = self.User.objects.get(username='carlos_profesor')
        profesor = Instructor.objects.get(user=usuario)
        solicitud.refresh_from_db()
        self.assertEqual(usuario.rol, self.User.Roles.INSTRUCTOR)
        self.assertFalse(usuario.is_staff)
        self.assertTrue(usuario.check_password('ClaveSegura123!'))
        self.assertEqual(profesor.documento, '1234567')
        self.assertTrue(profesor.activo)
        self.assertEqual(solicitud.estado, SolicitudRegistroProfesor.Estados.APROBADO)

    def test_configuracion_combina_rol_administrador_y_perfil_profesor(self):
        usuario = self.User.objects.create_user(
            username='admin_profesor_config',
            password='Clave123!',
            rol=self.User.Roles.ADMIN,
            is_staff=True,
        )
        Alumno.objects.create(user=usuario, documento='99887766')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:editar_perfil_usuario', args=[usuario.id]),
            {
                'rol': self.User.Roles.ADMIN,
                'cuenta_activa': 'on',
                'es_profesor': 'on',
                'especialidad': 'MMA',
                'profesor_activo': 'on',
            },
        )

        self.assertRedirects(response, reverse('gestion:configurar_perfiles'))
        usuario.refresh_from_db()
        self.assertEqual(usuario.rol, self.User.Roles.ADMIN)
        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.perfil_instructor.activo)
        self.assertEqual(usuario.perfil_instructor.especialidad, 'MMA')

    def test_profesor_normal_no_puede_administrar_perfiles(self):
        usuario = self.User.objects.create_user(
            username='profesor_sin_admin',
            password='Clave123!',
            rol=self.User.Roles.INSTRUCTOR,
        )
        Instructor.objects.create(
            user=usuario,
            documento='PROF-100',
            especialidad='Jiu Jitsu',
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse('gestion:configurar_perfiles'))

        self.assertEqual(response.status_code, 403)
