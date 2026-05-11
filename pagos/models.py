from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from finanzas.models import CuentaFinanciera


class MetodoPagoQR(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    titular = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    imagen_qr = models.ImageField(upload_to='qr_pagos/')
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    cuenta_financiera = models.ForeignKey(
        CuentaFinanciera,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='metodos_pago'
    )

    class Meta:
        verbose_name = 'Método de pago QR'
        verbose_name_plural = 'Métodos de pago QR'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Pago(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        APROBADO = 'APROBADO', 'Aprobado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'

    alumno = models.ForeignKey(
        'alumnos.Alumno',
        on_delete=models.CASCADE,
        related_name='pagos'
    )
    suscripcion = models.ForeignKey(
        'planes.Suscripcion',
        on_delete=models.CASCADE,
        related_name='pagos'
    )
    metodo_qr = models.ForeignKey(
        MetodoPagoQR,
        on_delete=models.PROTECT,
        related_name='pagos'
    )
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    comprobante = models.FileField(upload_to='comprobantes_pagos/')
    referencia_pago = models.CharField(max_length=100, blank=True, null=True)
    fecha_reporte = models.DateTimeField(auto_now_add=True)
    fecha_validacion = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.PENDIENTE
    )
    observacion_admin = models.TextField(blank=True, null=True)
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_validados'
    )

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        ordering = ['-fecha_reporte']

    def clean(self):
        if self.suscripcion_id and self.alumno_id:
            if self.suscripcion.alumno_id != self.alumno_id:
                raise ValidationError({
                    'suscripcion': 'La suscripción seleccionada no pertenece al alumno indicado.'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.alumno} - {self.valor} - {self.estado}"
