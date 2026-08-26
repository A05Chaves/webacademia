from django.test import Client, TestCase


class ConfiguracionCsrfTests(TestCase):
    def test_acepta_post_desde_dominio_publico_atendido_por_pythonanywhere(self):
        cliente = Client(enforce_csrf_checks=True)
        respuesta_get = cliente.get(
            '/login/',
            HTTP_HOST='alfredochaves.pythonanywhere.com',
            secure=True,
        )
        token = respuesta_get.cookies['csrftoken'].value

        respuesta_post = cliente.post(
            '/login/',
            {'username': 'no-existe', 'password': 'no-valida', 'csrfmiddlewaretoken': token},
            HTTP_HOST='alfredochaves.pythonanywhere.com',
            HTTP_ORIGIN='https://bjj.lu-a.com',
            secure=True,
        )

        self.assertEqual(respuesta_post.status_code, 200)
