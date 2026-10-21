from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from alumnos.models import Alumno
from gestion.forms import PagoAlumnoForm, ValidarPagoForm
from notificaciones.models import Notificacion
from planes.models import Plan, Suscripcion
from .models import Pago, MetodoPagoQR


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class CambiosPlanTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='admin_cambio', is_staff=True, rol='ADMIN', email='admin@example.test')
        self.usuario = User.objects.create_user(username='alumno_cambio', email='alumno@example.test')
        self.profesor = User.objects.create_user(username='prof_cambio', is_staff=True, rol='INSTRUCTOR', email='profe@example.test')
        self.alumno = Alumno.objects.create(user=self.usuario, documento='CAMBIO123')
        self.anterior = Plan.objects.create(nombre='Plan anterior', precio=100000, duracion_dias=30, clases_mes=8, clases_semana=2)
        self.nuevo = Plan.objects.create(nombre='Plan nuevo', precio=150000, duracion_dias=30, clases_mes=12, clases_semana=3)
        self.vigente = Suscripcion.objects.create(alumno=self.alumno, plan=self.anterior, fecha_inicio=timezone.localdate()-timedelta(days=10), fecha_vencimiento=timezone.localdate()+timedelta(days=19), estado='ACTIVA')
        self.metodo = MetodoPagoQR.objects.create(nombre='Caja cambio', titular='Academia', imagen_qr='qr.png')
        self.client.force_login(self.usuario)

    def datos(self, cambiar=True):
        datos = {'plan': self.nuevo.pk, 'valor': '150000', 'mensualidades':1, 'metodo_qr':self.metodo.pk, 'tipo_ajuste':'NORMAL'}
        if cambiar:datos['cambiar_plan']='on'
        return datos

    def archivo(self):
        return SimpleUploadedFile('pago.pdf', b'%PDF-1.4\n%%EOF')

    def registrar(self):
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.post(reverse('gestion:registrar_pago_alumno'), {**self.datos(), 'comprobante':self.archivo()})
        self.assertEqual(response.status_code,302)
        return Pago.objects.get()

    def test_plan_actual_predeterminado_y_cambio_explicito(self):
        form=PagoAlumnoForm(alumno=self.alumno)
        self.assertEqual(form['plan'].value(),self.anterior.pk)
        form=PagoAlumnoForm(self.datos(False),{'comprobante':self.archivo()},alumno=self.alumno)
        self.assertFalse(form.is_valid());self.assertIn('plan',form.errors)
        form=PagoAlumnoForm(self.datos(),{'comprobante':self.archivo()},alumno=self.alumno)
        self.assertTrue(form.is_valid(),form.errors)

    def test_sin_suscripcion_puede_elegir_primer_plan(self):
        self.vigente.delete()
        form=PagoAlumnoForm(self.datos(False),{'comprobante':self.archivo()},alumno=self.alumno)
        self.assertTrue(form.is_valid(),form.errors)

    def test_solicitud_avisa_al_estudiante_y_admin_no_al_profesor(self):
        pago=self.registrar()
        self.assertTrue(pago.cambio_plan_solicitado);self.assertEqual(pago.plan_anterior,self.anterior)
        self.assertEqual(Notificacion.objects.filter(pago=pago,estado='ENVIADA').count(),2)
        destinos={destino for mensaje in mail.outbox for destino in mensaje.to}
        self.assertEqual(destinos,{'admin@example.test','alumno@example.test'})
        self.vigente.refresh_from_db();self.assertEqual(self.vigente.estado,'ACTIVA')
        self.assertEqual(Suscripcion.objects.count(),1)

    def test_aprobacion_programa_nuevo_plan_y_avisa_fecha_y_limites(self):
        pago=self.registrar();self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('gestion:validar_pago',args=[pago.pk]),{'estado':'APROBADO'})
        pago.refresh_from_db()
        self.assertEqual(pago.suscripcion.estado,'PROGRAMADA')
        self.assertEqual(pago.suscripcion.fecha_inicio,self.vigente.fecha_vencimiento+timedelta(days=1))
        self.assertEqual(pago.suscripcion.plan,self.nuevo)
        aviso=Notificacion.objects.get(pago=pago,tipo='CAMBIO_PLAN_RESULTADO')
        self.assertEqual(aviso.estado,'ENVIADA');self.assertIn('Clases por mes: 12',aviso.mensaje)
        self.assertIn(pago.suscripcion.fecha_inicio.strftime('%d/%m/%Y'),aviso.mensaje)
        self.vigente.refresh_from_db();self.assertEqual(self.vigente.estado,'ACTIVA')

    def test_no_puede_anticipar_cambio_sobre_cobertura_pagada(self):
        pago=self.registrar()
        form=ValidarPagoForm({'estado':'APROBADO','fecha_inicio_manual':'on','fecha_inicio':timezone.localdate().isoformat()},instance=pago)
        self.assertFalse(form.is_valid());self.assertIn('fecha_inicio',form.errors)

    def test_rechazo_avisa_y_no_modifica_plan_actual(self):
        pago=self.registrar();self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('gestion:validar_pago',args=[pago.pk]),{'estado':'RECHAZADO','observacion_admin':'Soporte incorrecto'})
        aviso=Notificacion.objects.get(pago=pago,tipo='CAMBIO_PLAN_RESULTADO')
        self.assertIn('rechazado',aviso.titulo);self.assertIn('Soporte incorrecto',aviso.mensaje)
        self.assertEqual(Suscripcion.objects.count(),1)

    def test_fallo_correo_no_pierde_pago_y_se_puede_reintentar(self):
        with patch('pagos.cambios_plan.send_mail',side_effect=RuntimeError('SMTP no disponible')):
            pago=self.registrar()
        self.assertEqual(pago.estado,'PENDIENTE')
        self.assertEqual(Notificacion.objects.filter(pago=pago,estado='FALLIDA').count(),2)
        call_command('reenviar_cambios_plan',verbosity=0)
        self.assertEqual(Notificacion.objects.filter(pago=pago,estado='ENVIADA').count(),2)
