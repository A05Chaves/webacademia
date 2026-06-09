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
        OTRA = 'OTRA', 'Otra'

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
        related_name='asistencias'
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
        unique_together = ('alumno', 'clase', 'fecha_clase')
        ordering = ['-fecha_clase', '-fecha_confirmacion']

    def __str__(self):
        return f"{self.alumno} - {self.clase} - {self.fecha_clase}"
