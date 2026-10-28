from datetime import time
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from clases.models import ClaseProgramada, DisciplinaAcademia
from instructores.models import Instructor
from gestion.forms import ClaseProgramadaForm


class DisciplinasAcademiaTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username='admin_disciplinas', is_staff=True, rol='ADMIN')
        self.profesor = Instructor.objects.create(user=self.admin, documento='DOC_DISC', especialidad='Jiu Jitsu')
        self.clase = ClaseProgramada.objects.create(dia='LUNES',hora_inicio=time(10),hora_fin=time(11),disciplina='JIU_JITSU',instructor=self.profesor)
        self.disciplina = DisciplinaAcademia.objects.get(codigo='JIU_JITSU')
        self.client.force_login(self.admin)

    def test_nombre_se_edita_sin_cambiar_clases(self):
        response=self.client.post(reverse('gestion:editar_disciplina_academia',args=[self.disciplina.pk]),{'nombre':'Jiu Jitsu Brasilero','activa':'on'})
        self.assertRedirects(response,reverse('gestion:configurar_disciplinas'))
        self.clase.refresh_from_db()
        self.assertEqual(self.clase.disciplina,'JIU_JITSU')
        self.assertEqual(self.clase.get_disciplina_display(),'Jiu Jitsu Brasilero')
        self.assertIn(('JIU_JITSU','Jiu Jitsu Brasilero'),list(ClaseProgramadaForm().fields['disciplina'].choices))

    def test_inactiva_se_conserva_en_clase_existente(self):
        self.client.post(reverse('gestion:editar_disciplina_academia',args=[self.disciplina.pk]),{'nombre':self.disciplina.nombre})
        nuevas=dict(ClaseProgramadaForm().fields['disciplina'].choices)
        anteriores=dict(ClaseProgramadaForm(instance=self.clase).fields['disciplina'].choices)
        self.assertNotIn('JIU_JITSU',nuevas)
        self.assertIn('JIU_JITSU',anteriores)
        self.assertTrue(ClaseProgramada.objects.filter(pk=self.clase.pk).exists())

    def test_no_acepta_nombre_duplicado(self):
        response=self.client.post(reverse('gestion:editar_disciplina_academia',args=[self.disciplina.pk]),{'nombre':'muay thai','activa':'on'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Ya existe una disciplina')

    def test_estudiante_no_puede_editar(self):
        usuario=get_user_model().objects.create_user(username='alumno_disciplina')
        self.client.force_login(usuario)
        self.assertNotEqual(self.client.get(reverse('gestion:configurar_disciplinas')).status_code,200)
        self.client.post(reverse('gestion:editar_disciplina_academia',args=[self.disciplina.pk]),{'nombre':'No permitido'})
        self.disciplina.refresh_from_db();self.assertEqual(self.disciplina.nombre,'Jiu Jitsu')
