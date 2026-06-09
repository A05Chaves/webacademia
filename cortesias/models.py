from django.db import models
from django.utils import timezone


class ConsentimientoFirmado(models.Model):
    class Tipos(models.TextChoices):
        ADULTO = 'ADULTO', 'Adulto'
        MENOR = 'MENOR', 'Menor de edad'

    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    nombre_estudiante = models.CharField(max_length=150)
    documento_estudiante = models.CharField(
        max_length=30, blank=True, null=True)
    nombre_acudiente = models.CharField(max_length=150, blank=True, null=True)
    documento_acudiente = models.CharField(
        max_length=30, blank=True, null=True)
    texto_aceptado = models.TextField()
    firma_base64 = models.TextField()
    fecha_firma = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.nombre_estudiante} - {self.tipo}"


class ClaseCortesia(models.Model):
    class TiposPersona(models.TextChoices):
        ADULTO = 'ADULTO', 'Adulto'
        MENOR = 'MENOR', 'Menor de edad'

    clase = models.ForeignKey(
        'clases.ClaseProgramada',
        on_delete=models.CASCADE,
        related_name='cortesias'
    )

    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    documento = models.CharField(max_length=30, blank=True, null=True)
    telefono = models.CharField(max_length=30)
    correo = models.EmailField(blank=True, null=True)
    edad = models.PositiveIntegerField()

    tipo_persona = models.CharField(
        max_length=20,
        choices=TiposPersona.choices
    )

    eps = models.CharField(max_length=150, blank=True, null=True)

    condicion_medica = models.TextField(
        blank=True,
        null=True,
        verbose_name='Discapacidad, lesión o enfermedad importante'
    )

    nombre_acudiente = models.CharField(max_length=150, blank=True, null=True)
    documento_acudiente = models.CharField(
        max_length=30, blank=True, null=True)
    telefono_acudiente = models.CharField(max_length=30, blank=True, null=True)

    parentesco_acudiente = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    consentimiento = models.OneToOneField(
        ConsentimientoFirmado,
        on_delete=models.PROTECT,
        related_name='clase_cortesia'
    )

    contactado = models.BooleanField(default=False)

    se_convirtio = models.BooleanField(default=False)

    observacion_seguimiento = models.TextField(
        blank=True,
        null=True
    )

    fecha_contacto = models.DateTimeField(
        blank=True,
        null=True
    )

    fecha_registro = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.nombres} {self.apellidos} - Cortesía"
