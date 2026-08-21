from django.db import models
from django.utils import timezone


class CuentaFinanciera(models.Model):
    class Tipos(models.TextChoices):
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        BANCO = 'BANCO', 'Banco'
        BILLETERA = 'BILLETERA', 'Billetera digital'
        OTRO = 'OTRO', 'Otro'

    nombre = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    saldo_inicial = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    activa = models.BooleanField(default=True)

    @property
    def saldo_actual(self):
        ingresos = self.movimientos.filter(tipo='INGRESO').aggregate(
            total=models.Sum('valor')
        )['total'] or 0

        egresos = self.movimientos.filter(tipo='EGRESO').aggregate(
            total=models.Sum('valor')
        )['total'] or 0

        return self.saldo_inicial + ingresos - egresos

    def __str__(self):
        return self.nombre


# AUDITORIA DE GASTOS

class CategoriaFinanciera(models.Model):
    class Tipos(models.TextChoices):
        INGRESO = 'INGRESO', 'Ingreso'
        EGRESO = 'EGRESO', 'Egreso'
        AMBOS = 'AMBOS', 'Ambos'

    class Naturalezas(models.TextChoices):
        OPERACIONAL = 'OPERACIONAL', 'Operacional'
        NO_OPERACIONAL = 'NO_OPERACIONAL', 'No operacional'

    nombre = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(
        max_length=20,
        choices=Tipos.choices,
        default=Tipos.EGRESO
    )
    naturaleza = models.CharField(
        max_length=20,
        choices=Naturalezas.choices,
        default=Naturalezas.OPERACIONAL,
    )
    descripcion = models.CharField(max_length=250, blank=True)
    activa = models.BooleanField(default=True)
    creado = models.DateTimeField(default=timezone.now, editable=False)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Categoría financiera'
        verbose_name_plural = 'Categorías financieras'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class MovimientoFinanciero(models.Model):
    class Tipos(models.TextChoices):
        INGRESO = 'INGRESO', 'Ingreso'
        EGRESO = 'EGRESO', 'Egreso'
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia'

    cuenta = models.ForeignKey(
        CuentaFinanciera,
        on_delete=models.PROTECT,
        related_name='movimientos'
    )
    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    categoria = models.ForeignKey(
        CategoriaFinanciera,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movimientos'
    )
    concepto = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(default=timezone.now)
    pago = models.OneToOneField(
        'pagos.Pago',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimiento_financiero'
    )
    evento = models.ForeignKey(
        'pagos.Evento',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movimientos_financieros',
        help_text='Evento específico que originó este ingreso o gasto.',
    )
    observaciones = models.TextField(blank=True, null=True)
    soporte = models.FileField(
        upload_to='finanzas/academia/soportes/%Y/%m/',
        blank=True,
        null=True,
        help_text='Factura, recibo, comprobante, imagen o PDF relacionado.',
    )

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.tipo} - {self.cuenta} - {self.valor}"


class PagoProgramado(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        PAGADO = 'PAGADO', 'Pagado'
        VENCIDO = 'VENCIDO', 'Vencido'
        CANCELADO = 'CANCELADO', 'Cancelado'

    concepto = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_vencimiento = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.PENDIENTE
    )
    cuenta_pago = models.ForeignKey(
        CuentaFinanciera,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='pagos_programados'
    )
    fecha_pago = models.DateTimeField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['fecha_vencimiento']

    def __str__(self):
        return f"{self.concepto} - {self.estado}"
