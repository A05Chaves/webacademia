from django.db import models
from django.utils import timezone


class RegistroLegalEstudiante(models.Model):
    class TipoEstudiante(models.TextChoices):
        ADULTO = 'ADULTO', 'Adulto'
        MENOR = 'MENOR', 'Menor de edad'

    class Estados(models.TextChoices):
        PENDIENTE_VALIDACION = 'PENDIENTE_VALIDACION', 'Pendiente de validación'
        APROBADO = 'APROBADO', 'Aprobado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'

    tipo_estudiante = models.CharField(
        max_length=20,
        choices=TipoEstudiante.choices
    )

    foto = models.ImageField(
        upload_to='registros_estudiantes/fotos/',
        blank=True,
        null=True
    )

    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    documento = models.CharField(max_length=30)
    fecha_nacimiento = models.DateField()
    direccion = models.CharField(max_length=255)
    celular = models.CharField(max_length=30)
    correo = models.EmailField(blank=True, null=True)
    fecha_ingreso = models.DateField(default=timezone.now)

    plan_interes = models.ForeignKey(
        'planes.Plan',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='registros_interesados'
    )

    contacto_emergencia_nombre = models.CharField(max_length=150)
    contacto_emergencia_celular = models.CharField(max_length=30)

    eps = models.CharField(max_length=150)
    condicion_medica = models.TextField()

    nombre_acudiente = models.CharField(max_length=150, blank=True, null=True)
    documento_acudiente = models.CharField(
        max_length=30, blank=True, null=True)
    parentesco_acudiente = models.CharField(
        max_length=50, blank=True, null=True)
    celular_acudiente = models.CharField(max_length=30, blank=True, null=True)

    acepta_reglamento = models.BooleanField(default=False)
    acepta_riesgos = models.BooleanField(default=False)
    autoriza_imagen = models.BooleanField(default=False)

    texto_consentimiento = models.TextField()
    firma_base64 = models.TextField()

    fecha_firma = models.DateTimeField(default=timezone.now)
    ip_firma = models.GenericIPAddressField(blank=True, null=True)

    estado = models.CharField(
        max_length=30,
        choices=Estados.choices,
        default=Estados.PENDIENTE_VALIDACION
    )

    observacion_admin = models.TextField(blank=True, null=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Registro legal de estudiante'
        verbose_name_plural = 'Registros legales de estudiantes'
        ordering = ['-creado']

    def __str__(self):
        return f"{self.nombres} {self.apellidos} - {self.tipo_estudiante}"
