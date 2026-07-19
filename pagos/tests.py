import base64
from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageDraw

from alumnos.models import Alumno
from finanzas.models import CuentaFinanciera
from planes.models import Plan, Suscripcion
from gestion.forms import EventoForm

from .models import (
    AcademiaCompetidora, CategoriaEvento, Evento, InscripcionEvento,
    MetodoPagoQR, Pago, Promocion,
)
from .services import marcar_posible_duplicado


def imagen_prueba(nombre='foto.png'):
    salida = BytesIO()
    imagen = Image.new('RGB', (120, 120), 'white')
    ImageDraw.Draw(imagen).line((10, 100, 110, 20), fill='black', width=5)
    imagen.save(salida, format='PNG')
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type='image/png')


def firma_visible():
    archivo = imagen_prueba('firma.png')
    return 'data:image/png;base64,' + base64.b64encode(archivo.read()).decode()


class PagosAcademiaNuevosFlujosTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.override = self.settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media.cleanup)
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_user(
            username='admin-nuevos-pagos', password='clave-admin', is_staff=True
        )
        self.usuario = Usuario.objects.create_user(
            username='alumno-nuevos-pagos', password='clave-alumno',
            email='alumno@galeras.test', telefono='3001112233',
        )
        self.alumno = Alumno.objects.create(
            user=self.usuario,
            documento='EST-900',
            fecha_nacimiento=timezone.localdate().replace(year=1995),
            nombre_acudiente='Acudiente Prueba',
            documento_acudiente='ACU-777',
        )
        self.plan = Plan.objects.create(
            nombre='Mensual pruebas nuevas', precio=120000, duracion_dias=30
        )
        self.cuenta = CuentaFinanciera.objects.create(
            nombre='Cuenta pagos nuevos', tipo=CuentaFinanciera.Tipos.BANCO
        )
        self.metodo = MetodoPagoQR.objects.create(
            nombre='QR pagos nuevos', titular='Galeras BJJ',
            imagen_qr=SimpleUploadedFile('qr.png', b'qr'),
            cuenta_financiera=self.cuenta,
        )

    def nuevo_pago(self, nombre='pago.pdf', contenido=b'%PDF-comprobante'):
        pago = Pago(
            alumno=self.alumno,
            plan=self.plan,
            metodo_qr=self.metodo,
            valor=120000,
            comprobante=SimpleUploadedFile(nombre, contenido),
            referencia_pago='REF-900',
            pagador_documento='ACU-777',
        )
        marcar_posible_duplicado(pago)
        pago.save()
        return pago

    def test_marca_archivo_o_referencia_repetidos(self):
        primero = self.nuevo_pago()
        segundo = self.nuevo_pago(nombre='copia.pdf')

        self.assertFalse(primero.posible_duplicado)
        self.assertTrue(segundo.posible_duplicado)
        self.assertEqual(segundo.duplicado_de, primero)

    def test_aprobacion_usa_fecha_real_y_cuenta_dia_inicial(self):
        pago = self.nuevo_pago()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('gestion:validar_pago', args=[pago.id]),
            {'estado': Pago.Estados.APROBADO, 'fecha_inicio': '2026-07-01'},
        )

        self.assertRedirects(response, reverse('gestion:lista_pagos'))
        pago.refresh_from_db()
        self.assertEqual(pago.suscripcion.fecha_inicio.isoformat(), '2026-07-01')
        self.assertEqual(pago.suscripcion.fecha_vencimiento.isoformat(), '2026-07-30')
        self.assertTrue(pago.numero_comprobante.startswith('CP-'))

    def test_historial_filtra_por_documento_acudiente(self):
        self.nuevo_pago()
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('gestion:lista_pagos'), {'documento': 'ACU-777'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'REF-900')

    def test_promocion_publicada_aparece_en_home(self):
        hoy = timezone.localdate()
        promocion = Promocion.objects.create(
            nombre='Promoción visible', descripcion='Beneficio especial',
            plan=self.plan,
            tipo_beneficio=Promocion.TiposBeneficio.PORCENTAJE,
            valor_beneficio=10,
            fecha_inicio=hoy - timedelta(days=1),
            fecha_fin=hoy + timedelta(days=5),
            publicada_home=True,
        )
        response = self.client.get(reverse('gestion:home_publica'))
        self.assertContains(response, promocion.nombre)
        self.assertContains(response, 'Aplicar a la promoción')

    def test_evento_publicado_aparece_con_registro(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Seminario visible',
            descripcion='Seminario de pruebas',
            fecha_inicio=timezone.now() + timedelta(days=10),
            lugar='Galeras BJJ',
            precio_estudiante=50000,
            precio_externo=70000,
            publicada_home=True,
        )
        response = self.client.get(reverse('gestion:home_publica'))
        self.assertContains(response, evento.nombre)
        self.assertContains(response, 'Registrarme')

    def crear_torneo_gratuito(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Torneo categorías',
            descripcion='Torneo de prueba para llaves',
            fecha_inicio=timezone.now() + timedelta(days=20),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            alcance_torneo=Evento.AlcancesTorneo.ABIERTO,
            consentimiento_evento='Acepto los riesgos y reglas de este torneo.',
            reglamento_adultos='Reglamento competitivo para adultos.',
            reglamento_menores='Reglamento competitivo para menores y acudientes.',
        )
        categoria = CategoriaEvento.objects.create(
            evento=evento,
            nombre='Adulto ligero',
            genero=CategoriaEvento.Generos.MIXTA,
            edad_minima=18,
            peso_maximo=76,
            nivel='Principiante',
        )
        return evento, categoria

    def test_evento_gratuito_oculta_campos_de_pago(self):
        evento, categoria = self.crear_torneo_gratuito()

        response = self.client.get(
            reverse('gestion:inscribirse_evento', args=[evento.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, categoria.nombre)
        self.assertNotContains(response, 'name="metodo_qr"')
        self.assertNotContains(response, 'name="referencia_pago"')
        self.assertNotContains(response, 'name="comprobante"')

    def test_torneo_gratuito_confirma_categoria_sin_crear_pago(self):
        evento, categoria = self.crear_torneo_gratuito()

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Competidor Uno',
                'participante_documento': 'TOR-001',
                'fecha_nacimiento': '1995-05-10',
                'correo': 'competidor@example.com',
                'telefono': '3001234567',
                'categoria_evento': categoria.id,
                'peso': '74.50',
                'academia_origen': 'Academia visitante',
                'logo_academia': imagen_prueba('logo-visitante.png'),
                'foto_participante': imagen_prueba(),
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(
            evento=evento, participante_documento='TOR-001'
        )
        self.assertEqual(inscripcion.categoria_evento, categoria)
        self.assertEqual(inscripcion.estado, InscripcionEvento.Estados.CONFIRMADA)
        self.assertEqual(inscripcion.academia_origen, 'Academia visitante')
        self.assertTrue(inscripcion.foto_participante.name)
        self.assertEqual(
            inscripcion.texto_consentimiento, evento.consentimiento_evento
        )
        self.assertTrue(inscripcion.firma_base64.startswith('data:image/png;base64,'))
        self.assertIsNone(inscripcion.pago)
        self.assertFalse(Pago.objects.filter(tipo=Pago.Tipos.EVENTO).exists())

    def test_participante_reutiliza_academia_y_logo_registrados(self):
        evento, categoria = self.crear_torneo_gratuito()
        academia = AcademiaCompetidora.objects.create(
            nombre='Equipo ya registrado',
            logo=imagen_prueba('equipo-registrado.png'),
        )

        pagina = self.client.get(
            reverse('gestion:inscribirse_evento', args=[evento.id])
        )
        self.assertContains(pagina, 'Equipo ya registrado')
        self.assertContains(pagina, 'Mi academia no aparece en la lista')

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Participante con academia existente',
                'participante_documento': 'ACA-EXISTE-1',
                'fecha_nacimiento': '1995-05-10',
                'correo': 'academia-existente@example.com',
                'telefono': '3005554433',
                'academia_registrada': academia.id,
                'foto_participante': imagen_prueba('participante-existente.png'),
                'categoria_evento': categoria.id,
                'peso': '70',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(
            evento=evento, participante_documento='ACA-EXISTE-1'
        )
        self.assertEqual(inscripcion.academia_equipo, academia)
        self.assertEqual(inscripcion.academia_origen, academia.nombre)
        academia.refresh_from_db()
        self.assertTrue(academia.logo.name)
        self.assertEqual(
            inscripcion.texto_consentimiento, evento.consentimiento_evento
        )
        self.assertTrue(inscripcion.firma_base64.startswith('data:image/png;base64,'))
        self.assertIsNone(inscripcion.pago)
        self.assertFalse(Pago.objects.filter(tipo=Pago.Tipos.EVENTO).exists())

    def test_categoria_rechaza_peso_fuera_del_rango(self):
        evento, categoria = self.crear_torneo_gratuito()

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Competidor Pesado',
                'participante_documento': 'TOR-002',
                'fecha_nacimiento': '1990-01-01',
                'correo': 'pesado@example.com',
                'telefono': '3007654321',
                'categoria_evento': categoria.id,
                'peso': '80',
                'academia_origen': 'Academia visitante',
                'logo_academia': imagen_prueba('logo-peso.png'),
                'foto_participante': imagen_prueba(),
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'El peso supera el permitido')
        self.assertFalse(InscripcionEvento.objects.filter(evento=evento).exists())

    def test_llaves_reciben_solo_inscritos_confirmados_de_la_categoria(self):
        evento, categoria = self.crear_torneo_gratuito()
        otra_categoria = CategoriaEvento.objects.create(
            evento=evento, nombre='Adulto pesado', edad_minima=18,
        )
        datos = {
            'evento': evento,
            'fecha_nacimiento': timezone.localdate().replace(year=1990),
            'correo': 'llaves@example.com',
            'telefono': '3000000000',
            'acepta_consentimiento': True,
        }
        academia_norte = AcademiaCompetidora.objects.create(
            nombre='Academia Norte', logo=imagen_prueba('logo-norte.png')
        )
        InscripcionEvento.objects.create(
            **datos, categoria_evento=categoria,
            participante_nombre='Ana Confirmada', participante_documento='LL-1',
            academia_origen='Academia Norte',
            academia_equipo=academia_norte,
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        InscripcionEvento.objects.create(
            **datos, categoria_evento=categoria,
            participante_nombre='Pendiente No Cargar', participante_documento='LL-2',
            estado=InscripcionEvento.Estados.PENDIENTE,
        )
        InscripcionEvento.objects.create(
            **datos, categoria_evento=otra_categoria,
            participante_nombre='Otra Categoria', participante_documento='LL-3',
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        self.admin.is_superuser = True
        self.admin.save(update_fields=['is_superuser'])
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('gestion:cronometro_lucha'),
            {'evento': evento.id, 'categoria': categoria.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Ana Confirmada — Academia Norte', response.context['participantes_llave']
        )
        self.assertEqual(
            response.context['logos_llave']['Ana Confirmada — Academia Norte'],
            academia_norte.logo.url,
        )
        self.client.logout()
        logo_response = self.client.get(academia_norte.logo.url)
        self.assertEqual(logo_response.status_code, 200)
        logo_response.close()
        self.assertNotContains(response, 'Pendiente No Cargar')
        self.assertNotContains(response, 'Otra Categoria')
        self.assertContains(response, f'luchaBracket-categoria-{categoria.id}')

    def test_torneo_interno_recupera_datos_solo_con_documento(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Torneo interno',
            descripcion='Competencia de estudiantes',
            fecha_inicio=timezone.now() + timedelta(days=15),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            alcance_torneo=Evento.AlcancesTorneo.INTERNO,
            consentimiento_evento='Consentimiento exclusivo del torneo interno.',
            reglamento_adultos='Reglamento interno para adultos.',
            reglamento_menores='Reglamento interno para menores y acudientes.',
        )
        categoria = CategoriaEvento.objects.create(
            evento=evento, nombre='Interna adultos', edad_minima=18,
        )

        consulta = self.client.get(
            reverse('gestion:datos_estudiante_torneo', args=[evento.id]),
            {'documento': self.alumno.documento},
        )
        self.assertEqual(consulta.status_code, 200)
        self.assertEqual(consulta.json()['nombre'], str(self.alumno))
        self.assertTrue(consulta.json()['ficha_completa'])

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_documento': self.alumno.documento,
                'categoria_evento': categoria.id,
                'peso': '70',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(evento=evento)
        self.assertEqual(inscripcion.alumno, self.alumno)
        self.assertEqual(inscripcion.participante_nombre, str(self.alumno))
        self.assertEqual(inscripcion.correo, self.usuario.email)
        self.assertEqual(
            inscripcion.texto_consentimiento, evento.consentimiento_evento
        )
        self.assertEqual(inscripcion.texto_reglamento, evento.reglamento_adultos)
        self.assertTrue(inscripcion.firma_base64.startswith('data:image/png;base64,'))
        self.assertIsNotNone(inscripcion.fecha_firma)

    def test_inscripcion_de_menor_guarda_su_reglamento_especifico(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.TORNEO,
            nombre='Torneo abierto infantil',
            descripcion='Competencia para menores',
            fecha_inicio=timezone.now() + timedelta(days=25),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            publico=Evento.Publicos.MENORES,
            alcance_torneo=Evento.AlcancesTorneo.ABIERTO,
            consentimiento_evento='Consentimiento firmado por el acudiente.',
            reglamento_menores='Reglamento infantil especial.',
        )
        categoria = CategoriaEvento.objects.create(
            evento=evento, nombre='Infantil', edad_maxima=17,
        )

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Competidor Menor',
                'participante_documento': 'MEN-001',
                'fecha_nacimiento': '2013-06-01',
                'correo': 'acudiente@example.com',
                'telefono': '3004445566',
                'academia_origen': 'Academia Infantil',
                'logo_academia': imagen_prueba('logo-infantil.png'),
                'foto_participante': imagen_prueba(),
                'acudiente_nombre': 'Acudiente Responsable',
                'acudiente_documento': 'ACU-MEN-1',
                'acudiente_telefono': '3009998877',
                'categoria_evento': categoria.id,
                'peso': '40',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(evento=evento)
        self.assertEqual(inscripcion.texto_reglamento, evento.reglamento_menores)
        self.assertTrue(inscripcion.acepta_reglamento)
        self.assertEqual(inscripcion.acudiente_nombre, 'Acudiente Responsable')

    def test_imagen_del_evento_es_publica_sin_exponer_fotos_de_participantes(self):
        evento, _ = self.crear_torneo_gratuito()
        evento.imagen.save('afiche-torneo.png', imagen_prueba(), save=True)

        imagen_response = self.client.get(evento.imagen.url)
        self.assertEqual(imagen_response.status_code, 200)
        imagen_response.close()

        ruta_privada = default_storage.save(
            'eventos/participantes/foto-privada.png',
            ContentFile(imagen_prueba().read()),
        )
        privada_response = self.client.get('/media/' + ruta_privada)
        self.assertEqual(privada_response.status_code, 302)
        self.assertIn('/login/', privada_response.url)

        self.client.force_login(self.admin)
        privada_admin = self.client.get('/media/' + ruta_privada)
        self.assertEqual(privada_admin.status_code, 200)
        privada_admin.close()

    def test_video_corto_del_torneo_aparece_en_el_home(self):
        evento, _ = self.crear_torneo_gratuito()
        evento.publicada_home = True
        evento.video = SimpleUploadedFile(
            'promocion.mp4',
            b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom',
            content_type='video/mp4',
        )
        evento.save()

        response = self.client.get(reverse('gestion:home_publica'))

        self.assertContains(response, evento.video.url)
        self.assertContains(response, 'home-publication-video')
        video_response = self.client.get(evento.video.url)
        self.assertEqual(video_response.status_code, 200)
        video_response.close()

    def test_evento_en_curso_permanece_visible_hasta_su_fecha_final(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Evento actualmente en curso',
            descripcion='Debe continuar en el carrusel',
            fecha_inicio=timezone.now() - timedelta(days=1),
            fecha_fin=timezone.now() + timedelta(days=2),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
            publicada_home=True,
        )

        response = self.client.get(reverse('gestion:home_publica'))

        self.assertContains(response, evento.nombre)

    def test_fechas_de_inscripcion_son_independientes_del_evento(self):
        inicio_evento = timezone.localtime(timezone.now()) + timedelta(days=10)
        fin_evento = inicio_evento + timedelta(days=2)
        apertura = inicio_evento - timedelta(days=20)
        cierre = inicio_evento + timedelta(days=1)
        formato = '%Y-%m-%dT%H:%M'
        form = EventoForm(data={
            'tipo': Evento.Tipos.SEMINARIO,
            'nombre': 'Seminario con inscripción independiente',
            'descripcion': 'Prueba de calendario',
            'fecha_inicio': inicio_evento.strftime(formato),
            'fecha_fin': fin_evento.strftime(formato),
            'fecha_inicio_inscripcion': apertura.strftime(formato),
            'fecha_limite_inscripcion': cierre.strftime(formato),
            'lugar': 'Galeras BJJ',
            'precio_estudiante': '0',
            'precio_externo': '0',
            'publico': Evento.Publicos.TODOS,
            'alcance_torneo': Evento.AlcancesTorneo.INTERNO,
            'orden': '10',
            'activo': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_evento_no_recibe_inscripciones_antes_de_su_apertura(self):
        evento = Evento.objects.create(
            tipo=Evento.Tipos.SEMINARIO,
            nombre='Inscripción futura',
            descripcion='Aún no abre',
            fecha_inicio=timezone.now() + timedelta(days=20),
            fecha_inicio_inscripcion=timezone.now() + timedelta(days=2),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=10),
            lugar='Galeras BJJ',
            precio_estudiante=0,
            precio_externo=0,
        )

        self.assertFalse(evento.disponible)

    def test_correccion_del_formulario_exige_una_firma_nueva(self):
        evento, categoria = self.crear_torneo_gratuito()
        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Participante por corregir',
                'participante_documento': 'COR-001',
                'fecha_nacimiento': '1995-05-10',
                'correo': 'corregir@example.com',
                'telefono': '3005556677',
                'academia_origen': 'Academia Corrección',
                'logo_academia': imagen_prueba('logo-correccion.png'),
                'foto_participante': imagen_prueba(),
                'categoria_evento': categoria.id,
                # Se omite deliberadamente el peso.
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('peso', response.context['form'].errors)
        self.assertEqual(response.context['form']['firma_base64'].value(), '')
        self.assertFalse(InscripcionEvento.objects.filter(evento=evento).exists())

    def test_participante_de_18_anos_es_adulto_y_no_exige_acudiente(self):
        evento, categoria = self.crear_torneo_gratuito()
        hoy = timezone.localdate()
        nacimiento_adulto = hoy.replace(year=hoy.year - 18)
        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            {
                'participante_nombre': 'Adulto Recién Cumplido',
                'participante_documento': 'ADU-018',
                'fecha_nacimiento': nacimiento_adulto.isoformat(),
                'correo': 'adulto18@example.com',
                'telefono': '3001231818',
                'academia_origen': 'Academia Adultos',
                'logo_academia': imagen_prueba('logo-adultos.png'),
                'foto_participante': imagen_prueba(),
                'categoria_evento': categoria.id,
                'peso': '70',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            },
        )

        self.assertRedirects(response, reverse('gestion:home_publica'))
        inscripcion = InscripcionEvento.objects.get(evento=evento)
        self.assertEqual(inscripcion.acudiente_nombre, '')
        self.assertEqual(inscripcion.texto_reglamento, evento.reglamento_adultos)

    def test_administrador_puede_mover_participante_a_otra_categoria(self):
        evento, categoria_origen = self.crear_torneo_gratuito()
        categoria_destino = CategoriaEvento.objects.create(
            evento=evento,
            nombre='Adulto intermedio',
            edad_minima=18,
            peso_minimo=65,
            peso_maximo=80,
        )
        inscripcion = InscripcionEvento.objects.create(
            evento=evento,
            categoria_evento=categoria_origen,
            categoria=str(categoria_origen),
            participante_nombre='Competidor Movible',
            participante_documento='MOV-001',
            fecha_nacimiento=timezone.localdate().replace(year=1995),
            correo='mover@example.com',
            telefono='3007778899',
            academia_origen='Academia Móvil',
            peso=72,
            acepta_reglamento=True,
            acepta_consentimiento=True,
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:mover_inscripcion_categoria', args=[inscripcion.id]),
            {'categoria_evento': categoria_destino.id},
        )

        self.assertRedirects(
            response, reverse('gestion:inscripciones_evento', args=[evento.id])
        )
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.categoria_evento, categoria_destino)
        categoria_destino.refresh_from_db()
        self.assertEqual(inscripcion.categoria, str(categoria_destino))

    def test_administrador_puede_forzar_movimiento_fuera_del_rango_de_peso(self):
        evento, categoria_origen = self.crear_torneo_gratuito()
        categoria_destino = CategoriaEvento.objects.create(
            evento=evento,
            nombre='Peso superior administrativo',
            peso_minimo=80,
            peso_maximo=90,
        )
        inscripcion = InscripcionEvento.objects.create(
            evento=evento,
            categoria_evento=categoria_origen,
            categoria=str(categoria_origen),
            participante_nombre='Competidor fuera de rango',
            participante_documento='MOV-FORZADO',
            fecha_nacimiento=timezone.localdate().replace(year=1995),
            correo='forzado@example.com',
            telefono='3009998877',
            academia_origen='Academia Manual',
            peso=56,
            acepta_reglamento=True,
            acepta_consentimiento=True,
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('gestion:mover_inscripcion_categoria', args=[inscripcion.id]),
            {'categoria_evento': categoria_destino.id},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.categoria_evento, categoria_destino)
        self.assertContains(response, 'fue movido manualmente')

    def test_administrador_puede_editar_datos_del_participante(self):
        evento, categoria = self.crear_torneo_gratuito()
        firma_original = firma_visible()
        inscripcion = InscripcionEvento.objects.create(
            evento=evento,
            categoria_evento=categoria,
            categoria=str(categoria),
            participante_nombre='Nombre por corregir',
            participante_documento='EDIT-001',
            fecha_nacimiento=timezone.localdate().replace(year=1995),
            correo='anterior@example.com',
            telefono='3000000000',
            academia_origen='Academia anterior',
            peso=70,
            firma_base64=firma_original,
            acepta_reglamento=True,
            acepta_consentimiento=True,
            estado=InscripcionEvento.Estados.CONFIRMADA,
        )
        self.client.force_login(self.admin)

        pagina = self.client.get(
            reverse('gestion:editar_inscripcion_evento', args=[inscripcion.id])
        )
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Guardar cambios')
        self.assertContains(pagina, 'no reemplaza ni modifica')

        response = self.client.post(
            reverse('gestion:editar_inscripcion_evento', args=[inscripcion.id]),
            {
                'participante_nombre': 'Nombre Corregido',
                'participante_documento': 'EDIT-001',
                'fecha_nacimiento': inscripcion.fecha_nacimiento.isoformat(),
                'correo': 'corregido@example.com',
                'telefono': '3112223344',
                'academia_origen': 'Academia corregida',
                'acudiente_nombre': '',
                'acudiente_documento': '',
                'acudiente_telefono': '',
                'categoria_evento': categoria.id,
                'peso': '72.50',
                'estado': InscripcionEvento.Estados.CONFIRMADA,
            },
        )

        self.assertRedirects(
            response, reverse('gestion:inscripciones_evento', args=[evento.id])
        )
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.participante_nombre, 'Nombre Corregido')
        self.assertEqual(inscripcion.correo, 'corregido@example.com')
        self.assertEqual(str(inscripcion.peso), '72.50')
        self.assertEqual(inscripcion.academia_origen, 'Academia corregida')
        self.assertEqual(inscripcion.firma_base64, firma_original)

    def test_participante_puede_inscribirse_en_regular_y_superior(self):
        evento, categoria_regular = self.crear_torneo_gratuito()
        categoria_superior = CategoriaEvento.objects.create(
            evento=evento,
            nombre='División superior',
            tipo_categoria=CategoriaEvento.TiposCategoria.SUPERIOR,
            edad_minima=18,
            peso_maximo=88,
        )

        def datos(categoria, incluir_logo=False):
            data = {
                'participante_nombre': 'Competidor Doble',
                'participante_documento': 'DOB-001',
                'fecha_nacimiento': '1994-03-10',
                'correo': 'doble@example.com',
                'telefono': '3001212121',
                'academia_origen': 'Academia Doble',
                'foto_participante': imagen_prueba('competidor-doble.png'),
                'categoria_evento': categoria.id,
                'peso': '74',
                'acepta_reglamento': 'on',
                'acepta_consentimiento': 'on',
                'firma_base64': firma_visible(),
            }
            if incluir_logo:
                data['logo_academia'] = imagen_prueba('logo-doble.png')
            return data

        primera = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            datos(categoria_regular, incluir_logo=True),
        )
        segunda = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]),
            datos(categoria_superior),
        )

        self.assertRedirects(primera, reverse('gestion:home_publica'))
        self.assertRedirects(segunda, reverse('gestion:home_publica'))
        inscripciones = InscripcionEvento.objects.filter(
            evento=evento, participante_documento='DOB-001'
        )
        self.assertEqual(inscripciones.count(), 2)
        self.assertSetEqual(
            set(inscripciones.values_list('categoria_evento_id', flat=True)),
            {categoria_regular.id, categoria_superior.id},
        )
        self.assertEqual(
            AcademiaCompetidora.objects.filter(nombre='Academia Doble').count(), 1
        )

    def test_segunda_inscripcion_no_puede_ser_otra_categoria_regular(self):
        evento, categoria_regular = self.crear_torneo_gratuito()
        otra_regular = CategoriaEvento.objects.create(
            evento=evento, nombre='Otra división regular', edad_minima=18,
        )
        base = {
            'participante_nombre': 'Competidor Regular',
            'participante_documento': 'REG-002',
            'fecha_nacimiento': '1992-02-02',
            'correo': 'regular@example.com',
            'telefono': '3003434343',
            'academia_origen': 'Academia Regular',
            'foto_participante': imagen_prueba('regular-uno.png'),
            'categoria_evento': categoria_regular.id,
            'peso': '73',
            'acepta_reglamento': 'on',
            'acepta_consentimiento': 'on',
            'firma_base64': firma_visible(),
            'logo_academia': imagen_prueba('logo-regular.png'),
        }
        self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]), base
        )
        segundo = base.copy()
        segundo['categoria_evento'] = otra_regular.id
        segundo['foto_participante'] = imagen_prueba('regular-dos.png')
        segundo['firma_base64'] = firma_visible()
        segundo.pop('logo_academia')

        response = self.client.post(
            reverse('gestion:inscribirse_evento', args=[evento.id]), segundo
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La segunda inscripción debe ser')
        self.assertEqual(
            InscripcionEvento.objects.filter(
                evento=evento, participante_documento='REG-002'
            ).count(),
            1,
        )
