from django.db import models
from django.utils import timezone


class ClaseProgramada(models.Model):
    class DiasSemana(models.TextChoices):
        LUNES = 'LUNES', 'Lunes'
        MARTES = 'MARTES', 'Martes'
        MIERCOLES = 'MIERCOLES', 'Miércoles'
        JUEVES = 'JUEVES', 'Jueves'
        VIERNES = 'VIERNES', 'Viernes'
        SABADO = 'SABADO', 'Sábado'
        DOMINGO = 'DOMINGO', 'Domingo'

    class Disciplinas(models.TextChoices):
        JIU_JITSU = 'JIU_JITSU', 'Jiu Jitsu'
        MUAY_THAI = 'MUAY_THAI', 'Muay Thai'
        MMA = 'MMA', 'MMA'
        MMA_MUAYTHAI = 'MMA-MUAYTHAI', 'MMA & Muay Thai'
        OTRA = 'OTRA', 'Otra'

    class PublicosObjetivo(models.TextChoices):
        TODOS = 'TODOS', 'Adultos y menores'
        ADULTO = 'ADULTO', 'Adultos'
        MENOR = 'MENOR', 'Menores de edad'

    dia = models.CharField(
        max_length=20,
        choices=DiasSemana.choices
    )
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    disciplina = models.CharField(
        max_length=30,
        choices=Disciplinas.choices
    )

    # TITULO DE LA CLASE

    titulo = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    publico_objetivo = models.CharField(
        max_length=10,
        choices=PublicosObjetivo.choices,
        default=PublicosObjetivo.TODOS,
        verbose_name='Público objetivo',
    )

    instructor = models.ForeignKey(
        'instructores.Instructor',
        on_delete=models.PROTECT,
        related_name='clases'
    )
    cupo_maximo = models.PositiveIntegerField(default=20)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Clase programada'
        verbose_name_plural = 'Clases programadas'
        ordering = ['dia', 'hora_inicio']

    def __str__(self):
        return f"{self.dia} - {self.disciplina} - {self.hora_inicio}"


class AsistenciaClase(models.Model):
    class Estados(models.TextChoices):
        CONFIRMADA = 'CONFIRMADA', 'Confirmada'
        FUERA_DE_TIEMPO = 'FUERA_DE_TIEMPO', 'Fuera de tiempo'
        CANCELADA = 'CANCELADA', 'Cancelada'

    alumno = models.ForeignKey(
        'alumnos.Alumno',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='asistencias'
    )
    instructor = models.ForeignKey(
        'instructores.Instructor',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='asistencias',
    )
    clase = models.ForeignKey(
        ClaseProgramada,
        on_delete=models.CASCADE,
        related_name='asistencias'
    )
    fecha_clase = models.DateField()
    fecha_confirmacion = models.DateTimeField(default=timezone.now)
    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.CONFIRMADA
    )

    class Meta:
        verbose_name = 'Asistencia a clase'
        verbose_name_plural = 'Asistencias a clases'
        ordering = ['-fecha_clase', '-fecha_confirmacion']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(alumno__isnull=False, instructor__isnull=True)
                    | models.Q(alumno__isnull=True, instructor__isnull=False)
                ),
                name='asistencia_tiene_un_solo_perfil',
            ),
            models.UniqueConstraint(
                fields=['alumno', 'clase', 'fecha_clase'],
                condition=models.Q(alumno__isnull=False),
                name='asistencia_alumno_clase_fecha_unica',
            ),
            models.UniqueConstraint(
                fields=['instructor', 'clase', 'fecha_clase'],
                condition=models.Q(instructor__isnull=False),
                name='asistencia_instructor_clase_fecha_unica',
            ),
        ]

    @property
    def participante(self):
        return self.alumno or self.instructor

    @property
    def nombre_participante(self):
        return str(self.participante)

    @property
    def documento_participante(self):
        return self.participante.documento

    @property
    def tipo_participante(self):
        return 'Profesor' if self.instructor_id else 'Estudiante'

    def __str__(self):
        return f"{self.participante} - {self.clase} - {self.fecha_clase}"
