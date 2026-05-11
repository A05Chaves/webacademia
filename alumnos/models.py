from django.conf import settings
from django.db import models
from django.utils import timezone
import math


class Alumno(models.Model):
    class Disciplinas(models.TextChoices):
        JIU_JITSU_BRASILERO = 'JIU JISTU', 'Jiu Jitsu'
        MUAY_THAI = 'MUAY THAI', 'Muay Thai'
        MMA = 'MMA', 'MMA'
        OTRA = 'OTRA', 'Otra'

    class Estados(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        PROXIMO_VENCER = 'PROXIMO_VENCER', 'Próximo a vencer'
        VENCIDO = 'VENCIDO', 'Vencido'
        SUSPENDIDO = 'SUSPENDIDO', 'Suspendido'
        PENDIENTE = 'PENDIENTE', 'Pendiente'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_alumno'
    )
    documento = models.CharField(max_length=20, unique=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    disciplina = models.CharField(
        max_length=20,
        choices=Disciplinas.choices,
        default=Disciplinas.OTRA
    )
    grado = models.CharField(max_length=50, blank=True, null=True)
    nombre_acudiente = models.CharField(max_length=150, blank=True, null=True)
    telefono_acudiente = models.CharField(max_length=20, blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.ACTIVO
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Alumno'
        verbose_name_plural = 'Alumnos'
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        nombre = f"{self.user.first_name} {self.user.last_name}".strip()
        return nombre if nombre else self.user.username

    @property
    def suscripcion_actual(self):
        return self.suscripciones.order_by('-fecha_vencimiento').first()

    @property
    def fecha_vencimiento_actual(self):
        suscripcion = self.suscripcion_actual
        return suscripcion.fecha_vencimiento if suscripcion else None

    @property
    def dias_vencido(self):
        suscripcion = self.suscripcion_actual

        if not suscripcion:
            return 0

        hoy = timezone.now().date()

        if suscripcion.fecha_vencimiento < hoy:
            return (hoy - suscripcion.fecha_vencimiento).days

        return 0

    @property
    def mensualidades_pendientes(self):
        suscripcion = self.suscripcion_actual

        if not suscripcion:
            return 0

        if suscripcion.estado == 'PENDIENTE_PAGO':
            return 1

        dias = self.dias_vencido

        if dias <= 0:
            return 0

        duracion = suscripcion.plan.duracion_dias

        if duracion <= 0:
            return 0

        return math.ceil(dias / duracion)

    def actualizar_estado(self):
        suscripcion = self.suscripcion_actual

        if not suscripcion:
            self.estado = self.Estados.SUSPENDIDO

        elif suscripcion.estado == 'PENDIENTE_PAGO':
            self.estado = self.Estados.PENDIENTE

        else:
            dias = self.dias_para_vencer

            if dias is None:
                self.estado = self.Estados.SUSPENDIDO
            elif dias < 0:
                self.estado = self.Estados.VENCIDO
            elif dias <= 10:
                self.estado = self.Estados.PROXIMO_VENCER
            else:
                self.estado = self.Estados.ACTIVO

        self.save()

    @property
    def dias_para_vencer(self):
        suscripcion = self.suscripcion_actual

        if not suscripcion:
            return None

        from django.utils import timezone
        hoy = timezone.now().date()

        return (suscripcion.fecha_vencimiento - hoy).days
