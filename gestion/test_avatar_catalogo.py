from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from alumnos.models import Alumno
from .models import AvatarCatalogo, ArticuloAvatar, BilleteraMonedas, MovimientoMonedas


class AvatarCatalogoTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username='admin_avatar', is_staff=True)
        self.usuario = get_user_model().objects.create_user(username='estudiante_avatar', first_name='Lucía')
        self.alumno = Alumno.objects.create(user=self.usuario, documento='12345678')
        self.billetera = BilleteraMonedas.objects.create(usuario=self.usuario, saldo=125)
        self.client.force_login(self.admin)

    def test_panel_muestra_saldos_reales_y_no_los_modifica(self):
        response = self.client.get(reverse('gestion:avatares_panel'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lucía')
        self.assertEqual(response.context['total_monedas'], 125)
        self.billetera.refresh_from_db()
        self.assertEqual(self.billetera.saldo, 125)
        self.assertFalse(MovimientoMonedas.objects.exists())
        self.assertEqual(self.client.get(reverse('gestion:avatares_panel'), {'q': 'inexistente'}).context['alumnos'].paginator.count, 0)

    def test_catalogo_se_crea_edita_e_inhabilita_sin_cobrar(self):
        response = self.client.post(reverse('gestion:avatares_crear', args=['avatar']), {
            'nombre': 'Cuy deportista', 'publico': 'ADULTOS', 'precio': 300, 'activo': 'on',
        })
        self.assertRedirects(response, reverse('gestion:avatares_panel'))
        avatar = AvatarCatalogo.objects.get()
        response = self.client.post(reverse('gestion:avatares_crear', args=['articulo']), {
            'nombre': 'Uniforme azul', 'tipo': 'UNIFORME', 'publico': 'NINOS',
            'precio': 40, 'activo': 'on', 'avatar': avatar.pk,
        })
        self.assertRedirects(response, reverse('gestion:avatares_panel'))
        item = ArticuloAvatar.objects.get()
        self.client.post(reverse('gestion:avatares_editar', args=['articulo', item.pk]), {
            'nombre': item.nombre, 'tipo': item.tipo, 'publico': item.publico, 'precio': 45,
        })
        item.refresh_from_db()
        self.assertFalse(item.activo)
        self.billetera.refresh_from_db()
        self.assertEqual(self.billetera.saldo, 125)
        self.assertFalse(MovimientoMonedas.objects.exists())

    def test_impide_requisitos_circulares(self):
        item = ArticuloAvatar.objects.create(nombre='Mejora', tipo='MEJORA')
        response = self.client.post(reverse('gestion:avatares_editar', args=['articulo', item.pk]), {
            'nombre': item.nombre, 'tipo': 'MEJORA', 'publico': 'TODOS', 'precio': 10, 'requisito': item.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'requisitos circulares')

    def test_usuario_final_no_puede_configurar_catalogo(self):
        self.client.force_login(self.usuario)
        self.assertNotEqual(self.client.get(reverse('gestion:avatares_panel')).status_code, 200)
        self.client.post(reverse('gestion:avatares_crear', args=['avatar']), {
            'nombre': 'No autorizado', 'precio': 1, 'publico': 'TODOS',
        })
        self.assertFalse(AvatarCatalogo.objects.exists())
