from datetime import timedelta
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from alumnos.models import Alumno
from planes.models import Plan, Suscripcion
from gestion.forms import PagoAlumnoForm
from .models import Pago, MetodoPagoQR


@override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class PagoPendienteTests(TestCase):
    def setUp(self):
        self.usuario=get_user_model().objects.create_user(username='pendiente_mensual')
        self.alumno=Alumno.objects.create(user=self.usuario,documento='PEND123')
        self.plan=Plan.objects.create(nombre='Plan pendiente',precio=80000,duracion_dias=30)
        self.metodo=MetodoPagoQR.objects.create(nombre='Caja pendiente',titular='Academia',imagen_qr='qr.png')
        self.client.force_login(self.usuario)

    def pago(self,estado='PENDIENTE',tipo='MENSUALIDAD'):
        return Pago.objects.create(alumno=self.alumno,plan=self.plan,metodo_qr=self.metodo,valor=80000,comprobante='pago.pdf',estado=estado,tipo=tipo)

    def datos(self):
        return {'plan':self.plan.pk,'metodo_qr':self.metodo.pk,'valor':'80000','mensualidades':1,'comprobante':SimpleUploadedFile('nuevo.pdf',b'%PDF-1.4\n%%EOF')}

    def test_pendiente_bloquea_segundo_pago_y_muestra_aviso(self):
        anterior=self.pago()
        response=self.client.post(reverse('gestion:registrar_pago_alumno'),self.datos(),follow=True)
        self.assertEqual(Pago.objects.count(),1)
        self.assertContains(response,'Ya tienes un pago de mensualidad pendiente de validar')
        form=PagoAlumnoForm(alumno=self.alumno)
        self.assertEqual(form.pago_pendiente,anterior)

    def test_pendiente_promocion_tambien_bloquea(self):
        # Se simula el tipo en la consulta sin necesitar una promoción publicada.
        pago=self.pago();Pago.objects.filter(pk=pago.pk).update(tipo='PROMOCION')
        self.assertIsNotNone(PagoAlumnoForm(alumno=self.alumno).pago_pendiente)

    def test_evento_pendiente_no_bloquea_mensualidad(self):
        self.pago(tipo='EVENTO')
        self.client.post(reverse('gestion:registrar_pago_alumno'),self.datos())
        self.assertEqual(Pago.objects.count(),2)

    def test_pago_rechazado_o_aprobado_no_bloquea(self):
        for estado in ('RECHAZADO','APROBADO'):
            self.pago(estado=estado)
        self.assertIsNone(PagoAlumnoForm(alumno=self.alumno).pago_pendiente)

    def test_anticipo_considera_ultima_cobertura_programada(self):
        hoy=timezone.localdate()
        Suscripcion.objects.create(alumno=self.alumno,plan=self.plan,fecha_inicio=hoy-timedelta(days=10),fecha_vencimiento=hoy+timedelta(days=19),estado='ACTIVA')
        ultima=Suscripcion.objects.create(alumno=self.alumno,plan=self.plan,fecha_inicio=hoy+timedelta(days=20),fecha_vencimiento=hoy+timedelta(days=49),estado='PROGRAMADA')
        form=PagoAlumnoForm(alumno=self.alumno)
        self.assertTrue(form.cobertura_vigente)
        self.assertEqual(form.inicio_estimado,ultima.fecha_vencimiento+timedelta(days=1))
        self.assertEqual(form.cobertura_actual,ultima)

    def test_estado_se_actualiza_despues_de_aprobacion_sin_cache(self):
        pago=self.pago()
        url=reverse('gestion:estado_registro_pago')
        antes=self.client.get(url)
        self.assertEqual(antes.json()['pendiente']['id'],pago.pk)
        self.assertIn('no-store',antes['Cache-Control'])
        Pago.objects.filter(pk=pago.pk).update(estado='APROBADO')
        despues=self.client.get(url)
        self.assertIsNone(despues.json()['pendiente'])

    def test_estado_no_expone_datos_de_otro_estudiante(self):
        self.pago()
        usuario=get_user_model().objects.create_user(username='otro_estado')
        Alumno.objects.create(user=usuario,documento='OTRO_ESTADO')
        self.client.force_login(usuario)
        self.assertIsNone(self.client.get(reverse('gestion:estado_registro_pago')).json()['pendiente'])
        self.client.logout()
        self.assertEqual(self.client.get(reverse('gestion:estado_registro_pago')).status_code,403)
