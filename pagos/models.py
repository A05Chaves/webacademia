from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
import uuid

from config.file_validation import validate_short_video

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
        related_name='metodos_pago',
    )

    class Meta:
        verbose_name = 'Método de pago QR'
        verbose_name_plural = 'Métodos de pago QR'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Promocion(models.Model):
    class TiposBeneficio(models.TextChoices):
        PORCENTAJE = 'PORCENTAJE', 'Descuento porcentual'
        PRECIO_FIJO = 'PRECIO_FIJO', 'Precio fijo'
        DIAS_EXTRA = 'DIAS_EXTRA', 'Días adicionales'

    class Publicos(models.TextChoices):
        TODOS = 'TODOS', 'Todos los estudiantes'
        NUEVOS = 'NUEVOS', 'Estudiantes nuevos'
        ACTIVOS = 'ACTIVOS', 'Estudiantes activos'

    nombre = models.CharField(max_length=160)
    descripcion = models.TextField()
    plan = models.ForeignKey(
        'planes.Plan', on_delete=models.PROTECT, related_name='promociones'
    )
    tipo_beneficio = models.CharField(
        max_length=20, choices=TiposBeneficio.choices
    )
    valor_beneficio = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Porcentaje, precio fijo o número de días, según el beneficio.',
    )
    condiciones = models.TextField(blank=True)
    publico = models.CharField(
        max_length=20, choices=Publicos.choices, default=Publicos.TODOS
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    maximo_usos = models.PositiveIntegerField(blank=True, null=True)
    un_uso_por_alumno = models.BooleanField(default=True)
    imagen = models.ImageField(upload_to='promociones/', blank=True, null=True)
    video = models.FileField(
        upload_to='promociones/videos/',
        blank=True,
        null=True,
        validators=[validate_short_video],
        help_text='Video corto MP4 o WEBM, máximo 25 MB.',
    )
    publicada_home = models.BooleanField(default=False)
    destacada = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=10)
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['orden', '-fecha_inicio']

    @property
    def vigente(self):
        hoy = timezone.localdate()
        return self.activa and self.fecha_inicio <= hoy <= self.fecha_fin

    @property
    def precio_aplicado(self):
        if self.tipo_beneficio == self.TiposBeneficio.PORCENTAJE:
            return max(self.plan.precio * (1 - self.valor_beneficio / 100), 0)
        if self.tipo_beneficio == self.TiposBeneficio.PRECIO_FIJO:
            return self.valor_beneficio
        return self.plan.precio

    @property
    def dias_aplicados(self):
        if self.tipo_beneficio == self.TiposBeneficio.DIAS_EXTRA:
            return self.plan.duracion_dias + int(self.valor_beneficio)
        return self.plan.duracion_dias

    def __str__(self):
        return self.nombre


class Evento(models.Model):
    class Tipos(models.TextChoices):
        SEMINARIO = 'SEMINARIO', 'Seminario'
        TORNEO = 'TORNEO', 'Torneo'
        CAMPAMENTO = 'CAMPAMENTO', 'Campamento'
        OTRO = 'OTRO', 'Otro evento'

    class Publicos(models.TextChoices):
        TODOS = 'TODOS', 'Todo público'
        ADULTOS = 'ADULTOS', 'Adultos'
        MENORES = 'MENORES', 'Menores de edad'
        ESTUDIANTES = 'ESTUDIANTES', 'Solo estudiantes'

    class AlcancesTorneo(models.TextChoices):
        INTERNO = 'INTERNO', 'Interno: solo estudiantes de la academia'
        ABIERTO = 'ABIERTO', 'Abierto: participantes de otras academias'

    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    nombre = models.CharField(max_length=180)
    descripcion = models.TextField()
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField(blank=True, null=True)
    fecha_inicio_inscripcion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Inicio de inscripciones',
        help_text='Si se deja vacío, las inscripciones quedan abiertas inmediatamente.',
    )
    fecha_limite_inscripcion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Cierre de inscripciones',
        help_text='Es independiente de las fechas de inicio y finalización del evento.',
    )
    lugar = models.CharField(max_length=200)
    precio_estudiante = models.DecimalField(max_digits=12, decimal_places=2)
    precio_externo = models.DecimalField(max_digits=12, decimal_places=2)
    cupo_maximo = models.PositiveIntegerField(blank=True, null=True)
    publico = models.CharField(
        max_length=20, choices=Publicos.choices, default=Publicos.TODOS
    )
    requisitos = models.TextField(blank=True)
    alcance_torneo = models.CharField(
        max_length=15,
        choices=AlcancesTorneo.choices,
        default=AlcancesTorneo.INTERNO,
        help_text='Solo se aplica cuando el evento es un torneo.',
    )
    consentimiento_evento = models.TextField(
        blank=True,
        help_text=(
            'Texto que deberá aceptar y firmar cada participante. '
            'Puede ser diferente para cada evento.'
        ),
    )
    reglamento_adultos = models.TextField(
        blank=True,
        help_text='Reglamento que aceptarán los participantes mayores de edad.',
    )
    reglamento_menores = models.TextField(
        blank=True,
        help_text=(
            'Reglamento aplicable a menores y que deberá aceptar su acudiente.'
        ),
    )
    imagen = models.ImageField(upload_to='eventos/', blank=True, null=True)
    video = models.FileField(
        upload_to='eventos/videos/',
        blank=True,
        null=True,
        validators=[validate_short_video],
        help_text='Video corto MP4 o WEBM, máximo 25 MB.',
    )
    publicada_home = models.BooleanField(default=False)
    destacada = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=10)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fecha_inicio']

    @property
    def inscripciones_confirmadas(self):
        return self.inscripciones.filter(
            estado=InscripcionEvento.Estados.CONFIRMADA
        ).count()

    @property
    def cupos_disponibles(self):
        if self.cupo_maximo is None:
            return None
        return max(self.cupo_maximo - self.inscripciones_confirmadas, 0)

    @property
    def disponible(self):
        ahora = timezone.now()
        inscripciones_iniciadas = (
            not self.fecha_inicio_inscripcion
            or self.fecha_inicio_inscripcion <= ahora
        )
        inscripciones_no_cerradas = (
            not self.fecha_limite_inscripcion
            or self.fecha_limite_inscripcion >= ahora
        )
        return (
            self.activo
            and inscripciones_iniciadas
            and inscripciones_no_cerradas
            and self.cupos_disponibles != 0
        )

    def __str__(self):
        return self.nombre


class CategoriaEvento(models.Model):
    class Generos(models.TextChoices):
        MIXTA = 'MIXTA', 'Mixta'
        FEMENINA = 'FEMENINA', 'Femenina'
        MASCULINA = 'MASCULINA', 'Masculina'

    class TiposCategoria(models.TextChoices):
        REGULAR = 'REGULAR', 'Categoría regular'
        SUPERIOR = 'SUPERIOR', 'Categoría superior'
        ABSOLUTA = 'ABSOLUTA', 'Categoría absoluta'

    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name='categorias'
    )
    nombre = models.CharField(max_length=120)
    tipo_categoria = models.CharField(
        max_length=12,
        choices=TiposCategoria.choices,
        default=TiposCategoria.REGULAR,
        help_text=(
            'Solo una categoría superior o absoluta puede utilizarse como '
            'segunda inscripción del mismo participante.'
        ),
    )
    genero = models.CharField(
        max_length=15, choices=Generos.choices, default=Generos.MIXTA
    )
    edad_minima = models.PositiveSmallIntegerField(blank=True, null=True)
    edad_maxima = models.PositiveSmallIntegerField(blank=True, null=True)
    peso_minimo = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True
    )
    peso_maximo = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True
    )
    nivel = models.CharField(
        max_length=100, blank=True,
        help_text='Ejemplo: principiante, cinturón blanco o avanzado.',
    )
    cupo_maximo = models.PositiveIntegerField(blank=True, null=True)
    orden = models.PositiveIntegerField(default=10)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'nombre'],
                name='categoria_nombre_unico_por_evento',
            ),
        ]

    @property
    def inscritos_activos(self):
        return self.inscripciones.exclude(
            estado__in=(
                InscripcionEvento.Estados.RECHAZADA,
                InscripcionEvento.Estados.CANCELADA,
            )
        ).count()

    @property
    def cupos_disponibles(self):
        if self.cupo_maximo is None:
            return None
        return max(self.cupo_maximo - self.inscritos_activos, 0)

    def __str__(self):
        detalles = [self.nombre, self.get_genero_display()]
        if self.edad_minima is not None or self.edad_maxima is not None:
            minimo_edad = self.edad_minima if self.edad_minima is not None else 0
            maximo_edad = self.edad_maxima if self.edad_maxima is not None else '∞'
            detalles.append(f'{minimo_edad}-{maximo_edad} años')
        if self.nivel:
            detalles.append(self.nivel)
        if self.peso_minimo is not None or self.peso_maximo is not None:
            minimo = self.peso_minimo if self.peso_minimo is not None else 0
            maximo = self.peso_maximo if self.peso_maximo is not None else '∞'
            detalles.append(f'{minimo}-{maximo} kg')
        return ' · '.join(map(str, detalles))


class AcademiaCompetidora(models.Model):
    nombre = models.CharField(max_length=180)
    logo = models.ImageField(upload_to='academias/logos/', blank=True, null=True)
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(
                Lower('nombre'), name='academia_competidora_nombre_unico'
            ),
        ]

    def __str__(self):
        return self.nombre


class Pago(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        APROBADO = 'APROBADO', 'Aprobado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'

    class Tipos(models.TextChoices):
        MENSUALIDAD = 'MENSUALIDAD', 'Mensualidad'
        PROMOCION = 'PROMOCION', 'Mensualidad con promoción'
        EVENTO = 'EVENTO', 'Seminario, torneo o evento'
        OTRO = 'OTRO', 'Otro ingreso de academia'

    alumno = models.ForeignKey(
        'alumnos.Alumno',
        on_delete=models.CASCADE,
        related_name='pagos',
        blank=True,
        null=True,
    )
    suscripcion = models.ForeignKey(
        'planes.Suscripcion',
        on_delete=models.SET_NULL,
        related_name='pagos',
        blank=True,
        null=True,
    )
    plan = models.ForeignKey(
        'planes.Plan',
        on_delete=models.PROTECT,
        related_name='pagos',
        blank=True,
        null=True,
    )
    promocion = models.ForeignKey(
        Promocion,
        on_delete=models.PROTECT,
        related_name='pagos',
        blank=True,
        null=True,
    )
    tipo = models.CharField(
        max_length=20, choices=Tipos.choices, default=Tipos.MENSUALIDAD
    )
    metodo_qr = models.ForeignKey(
        MetodoPagoQR, on_delete=models.PROTECT, related_name='pagos'
    )
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    comprobante = models.FileField(upload_to='comprobantes_pagos/')
    referencia_pago = models.CharField(max_length=100, blank=True, null=True)
    pagador_nombre = models.CharField(max_length=180, blank=True)
    pagador_documento = models.CharField(max_length=30, blank=True, db_index=True)
    pagador_correo = models.EmailField(blank=True)
    comprobante_hash = models.CharField(max_length=64, blank=True, db_index=True)
    posible_duplicado = models.BooleanField(default=False)
    duplicado_de = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='posibles_duplicados',
    )
    justificacion_duplicado = models.TextField(blank=True)
    concepto_detalle = models.CharField(max_length=240, blank=True)
    numero_comprobante = models.CharField(
        max_length=30, unique=True, blank=True, null=True
    )
    token_comprobante = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False
    )
    fecha_comprobante = models.DateTimeField(blank=True, null=True)
    correo_comprobante_enviado_a = models.EmailField(blank=True)
    fecha_envio_comprobante = models.DateTimeField(blank=True, null=True)
    error_envio_comprobante = models.TextField(blank=True)
    fecha_reporte = models.DateTimeField(auto_now_add=True)
    fecha_validacion = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(
        max_length=20, choices=Estados.choices, default=Estados.PENDIENTE
    )
    observacion_admin = models.TextField(blank=True, null=True)
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_validados',
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
        if (
            self.tipo in (self.Tipos.MENSUALIDAD, self.Tipos.PROMOCION)
            and not self.suscripcion_id
            and not self.plan_id
        ):
            raise ValidationError({
                'plan': 'Debe seleccionar un plan para este pago.'
            })
        if self.tipo == self.Tipos.PROMOCION and not self.promocion_id:
            raise ValidationError({'promocion': 'Debe seleccionar la promoción aplicada.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        persona = self.alumno or self.pagador_nombre or 'Pago externo'
        return f'{persona} - {self.valor} - {self.estado}'


class AplicacionPromocion(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de revisión'
        APLICADA = 'APLICADA', 'Aplicada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    promocion = models.ForeignKey(
        Promocion, on_delete=models.PROTECT, related_name='aplicaciones'
    )
    alumno = models.ForeignKey(
        'alumnos.Alumno',
        on_delete=models.PROTECT,
        related_name='aplicaciones_promocion',
    )
    pago = models.OneToOneField(
        Pago, on_delete=models.PROTECT, related_name='aplicacion_promocion'
    )
    estado = models.CharField(
        max_length=20, choices=Estados.choices, default=Estados.PENDIENTE
    )
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada']


class InscripcionEvento(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de pago o revisión'
        CONFIRMADA = 'CONFIRMADA', 'Confirmada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'
        CANCELADA = 'CANCELADA', 'Cancelada'
        LISTA_ESPERA = 'LISTA_ESPERA', 'Lista de espera'

    evento = models.ForeignKey(
        Evento, on_delete=models.PROTECT, related_name='inscripciones'
    )
    alumno = models.ForeignKey(
        'alumnos.Alumno',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='inscripciones_eventos',
    )
    pago = models.OneToOneField(
        Pago,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='inscripcion_evento',
    )
    participante_nombre = models.CharField(max_length=180)
    participante_documento = models.CharField(max_length=30)
    fecha_nacimiento = models.DateField()
    correo = models.EmailField()
    telefono = models.CharField(max_length=30)
    academia_origen = models.CharField(max_length=180, blank=True)
    academia_equipo = models.ForeignKey(
        AcademiaCompetidora,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='inscripciones',
    )
    foto_participante = models.ImageField(
        upload_to='eventos/participantes/', blank=True, null=True
    )
    acudiente_nombre = models.CharField(max_length=180, blank=True)
    acudiente_documento = models.CharField(max_length=30, blank=True)
    acudiente_telefono = models.CharField(max_length=30, blank=True)
    categoria = models.CharField(max_length=100, blank=True)
    categoria_evento = models.ForeignKey(
        CategoriaEvento,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='inscripciones',
    )
    peso = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    acepta_consentimiento = models.BooleanField(default=False)
    texto_consentimiento = models.TextField(blank=True)
    acepta_reglamento = models.BooleanField(default=False)
    texto_reglamento = models.TextField(blank=True)
    firma_base64 = models.TextField(blank=True)
    fecha_firma = models.DateTimeField(blank=True, null=True)
    ip_firma = models.GenericIPAddressField(blank=True, null=True)
    estado = models.CharField(
        max_length=20, choices=Estados.choices, default=Estados.PENDIENTE
    )
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creada']
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'participante_documento', 'categoria_evento'],
                condition=(
                    ~Q(estado='CANCELADA') & Q(categoria_evento__isnull=False)
                ),
                name='inscripcion_categoria_documento_activa_unica',
            ),
            models.UniqueConstraint(
                fields=['evento', 'participante_documento'],
                condition=(
                    ~Q(estado='CANCELADA') & Q(categoria_evento__isnull=True)
                ),
                name='inscripcion_sin_categoria_documento_activa_unica',
            ),
        ]

    def __str__(self):
        return f'{self.evento} - {self.participante_nombre}'
