from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from alumnos.models import Alumno
from planes.models import Plan, Suscripcion
from finanzas.models import CuentaFinanciera, MovimientoFinanciero
from gestion.forms import PagoAlumnoForm
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Pago, MetodoPagoQR


class MensualidadesTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username='admin_meses', is_staff=True)
        self.usuario = get_user_model().objects.create_user(username='alumno_meses')
        self.alumno = Alumno.objects.create(user=self.usuario, documento='123MES')
        self.plan = Plan.objects.create(nombre='Mensual', precio=100000, duracion_dias=30)
        self.cuenta = CuentaFinanciera.objects.create(nombre='Caja meses', tipo='EFECTIVO')
        self.metodo = MetodoPagoQR.objects.create(nombre='Caja', titular='Academia', imagen_qr='qr.png', cuenta_financiera=self.cuenta)
        self.client.force_login(self.admin)

    def pago(self, valor=200000, ajuste='NORMAL', cobertura=2):
        return Pago.objects.create(alumno=self.alumno, plan=self.plan, metodo_qr=self.metodo,
            valor=valor, comprobante='meses.pdf', mensualidades=2,
            precio_mensualidad=100000, total_calculado=200000,
            tipo_ajuste=ajuste, motivo_ajuste='Acuerdo revisado' if ajuste!='NORMAL' else '',
            mensualidades_cobertura=cobertura,
            saldo_pendiente=200000-valor if ajuste=='ABONO' else 0)

    def aprobar(self, pago, cobertura=None, ajuste=None):
        datos={'estado':'APROBADO','tipo_ajuste':ajuste or pago.tipo_ajuste,'motivo_ajuste':pago.motivo_ajuste}
        if cobertura is not None:datos['mensualidades_cobertura']=cobertura
        return self.client.post(reverse('gestion:validar_pago', args=[pago.pk]), datos)

    def test_dos_mensualidades_cubren_60_dias_y_no_duplica_aprobacion(self):
        pago=self.pago();self.aprobar(pago);pago.refresh_from_db()
        self.assertEqual(pago.estado,'APROBADO')
        self.assertEqual((pago.suscripcion.fecha_vencimiento-pago.suscripcion.fecha_inicio).days,59)
        self.aprobar(pago)
        self.assertEqual(Suscripcion.objects.count(),1)
        self.assertEqual(MovimientoFinanciero.objects.filter(pago=pago).count(),1)

    def test_pago_completo_admite_motivo_y_observacion_vacios(self):
        pago=self.pago()
        response=self.client.post(reverse('gestion:validar_pago',args=[pago.pk]),{'estado':'APROBADO','tipo_ajuste':'NORMAL','motivo_ajuste':'','observacion_admin':''})
        self.assertEqual(response.status_code,302)
        pago.refresh_from_db();self.assertEqual(pago.estado,'APROBADO')

    def test_efectivo_no_exige_soporte_ni_referencia(self):
        datos={'plan':self.plan.pk,'metodo_qr':self.metodo.pk,'valor':'100000','mensualidades':1,'referencia_pago':'NO GUARDAR'}
        form=PagoAlumnoForm(datos)
        self.assertTrue(form.is_valid(),form.errors)
        pago=form.save(commit=False);pago.alumno=self.alumno;pago.save()
        self.assertFalse(pago.comprobante)
        self.assertEqual(pago.referencia_pago,'')

    def test_transferencia_sigue_exigiendo_soporte(self):
        banco=CuentaFinanciera.objects.create(nombre='Banco meses',tipo='BANCO')
        metodo=MetodoPagoQR.objects.create(nombre='Transferencia',titular='Academia',imagen_qr='qr.png',cuenta_financiera=banco)
        form=PagoAlumnoForm({'plan':self.plan.pk,'metodo_qr':metodo.pk,'valor':'100000','mensualidades':1})
        self.assertFalse(form.is_valid());self.assertIn('comprobante',form.errors)

    def test_decision_pendiente_muestra_resumen_de_error(self):
        pago=self.pago()
        response=self.client.post(reverse('gestion:validar_pago',args=[pago.pk]),{'estado':'PENDIENTE','tipo_ajuste':'NORMAL'})
        self.assertContains(response,'No se pudo guardar la revisión')
        self.assertContains(response,'no se puede guardar la revisión como Pendiente')
        self.assertContains(response,'id="errores-revision" class="alert alert-danger"')
        pago.refresh_from_db();self.assertEqual(pago.estado,'PENDIENTE')

    def test_abono_cubre_solo_un_mes_y_guarda_saldo(self):
        pago=self.pago(150000,'ABONO',1);self.aprobar(pago,1);pago.refresh_from_db()
        self.assertEqual((pago.suscripcion.fecha_vencimiento-pago.suscripcion.fecha_inicio).days,29)
        self.assertEqual(pago.saldo_pendiente,Decimal('50000'))

    def test_abono_menor_a_mensualidad_no_crea_suscripcion(self):
        pago=self.pago(50000,'ABONO',0);self.aprobar(pago,0);pago.refresh_from_db()
        self.assertEqual(pago.estado,'APROBADO');self.assertIsNone(pago.suscripcion)
        self.assertEqual(pago.saldo_pendiente,150000)

    def test_abono_no_puede_habilitar_dos_meses(self):
        pago=self.pago(150000,'ABONO',1);response=self.aprobar(pago,2)
        self.assertEqual(response.status_code,200)
        pago.refresh_from_db();self.assertEqual(pago.estado,'PENDIENTE')
        self.assertFalse(Suscripcion.objects.exists())

    def test_descuento_autorizado_cubre_dos_meses_sin_deuda(self):
        pago=self.pago(150000,'DESCUENTO',2);self.aprobar(pago);pago.refresh_from_db()
        self.assertEqual((pago.suscripcion.fecha_vencimiento-pago.suscripcion.fecha_inicio).days,59)
        self.assertEqual(pago.saldo_pendiente,0)

    def test_formulario_calcula_total_y_deja_clasificacion_al_administrador(self):
        datos={'plan':self.plan.pk,'metodo_qr':self.metodo.pk,'valor':'150000','mensualidades':2,'tipo_ajuste':'ABONO','motivo_ajuste':'Pago parcial'}
        form=PagoAlumnoForm(datos,{'comprobante':SimpleUploadedFile('prueba.pdf',b'%PDF-1.4\n%%EOF')})
        self.assertTrue(form.is_valid(),form.errors)
        pago=form.save(commit=False)
        self.assertEqual(pago.total_calculado,200000);self.assertEqual(pago.mensualidades_cobertura,1)
        datos['motivo_ajuste']=''
        form=PagoAlumnoForm(datos,{'comprobante':SimpleUploadedFile('prueba.pdf',b'%PDF-1.4\n%%EOF')})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.save(commit=False).tipo_ajuste,'OTRO')
        self.assertEqual(form.save(commit=False).saldo_pendiente,50000)
        datos['tipo_ajuste']='DESCUENTO'
        form=PagoAlumnoForm(datos,{'comprobante':SimpleUploadedFile('prueba.pdf',b'%PDF-1.4\n%%EOF')})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.save(commit=False).tipo_ajuste,'OTRO')
