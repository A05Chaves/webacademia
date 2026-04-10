from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Plan(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    duracion_dias = models.PositiveIntegerField()
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plan'
        verbose_name_plural = 'Planes'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} - ${self.precio}"


class Suscripcion(models.Model):
    class Estados(models.TextChoices):
        ACTIVA = 'ACTIVA', 'Activa'
        PENDIENTE_PAGO = 'PENDIENTE_PAGO', 'Pendiente de pago'
        VENCIDA = 'VENCIDA', 'Vencida'
        SUSPENDIDA = 'SUSPENDIDA', 'Suspendida'
        FINALIZADA = 'FINALIZADA', 'Finalizada'

    alumno = models.ForeignKey(
        'alumnos.Alumno',
        on_delete=models.CASCADE,
        related_name='suscripciones'
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='suscripciones'
    )
    fecha_inicio = models.DateField()
    fecha_vencimiento = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.PENDIENTE_PAGO
    )
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Suscripción'
        verbose_name_plural = 'Suscripciones'
        ordering = ['-fecha_vencimiento']
        constraints = [
            models.UniqueConstraint(
                fields=['alumno'],
                condition=Q(estado='ACTIVA'),
                name='unique_suscripcion_activa_por_alumno'
            )
        ]

    def clean(self):
        if self.fecha_vencimiento < self.fecha_inicio:
            raise ValidationError({
                'fecha_vencimiento': 'La fecha de vencimiento no puede ser anterior a la fecha de inicio.'
            })
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.alumno} - {self.plan.nombre} ({self.estado})"