from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class CuentaTienda(models.Model):
    class Tipos(models.TextChoices):
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        BANCO = 'BANCO', 'Banco'
        BILLETERA = 'BILLETERA', 'Billetera digital'
        OTRO = 'OTRO', 'Otro'

    nombre = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    saldo_inicial = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['-activa', 'nombre']
        verbose_name = 'Cuenta de tienda'
        verbose_name_plural = 'Cuentas de tienda'

    @property
    def saldo_actual(self):
        ingresos = self.movimientos.filter(
            tipo=MovimientoTienda.Tipos.INGRESO
        ).aggregate(total=models.Sum('valor'))['total'] or 0
        egresos = self.movimientos.filter(
            tipo=MovimientoTienda.Tipos.EGRESO
        ).aggregate(total=models.Sum('valor'))['total'] or 0
        return self.saldo_inicial + ingresos - egresos

    def __str__(self):
        return self.nombre


class ProductoTienda(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    referencia = models.CharField(
        max_length=60,
        unique=True,
        null=True,
        blank=True,
        help_text='Código o SKU opcional.',
    )
    descripcion = models.TextField(blank=True)
    precio_venta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    costo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    stock = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activo', 'nombre']
        verbose_name = 'Producto de tienda'
        verbose_name_plural = 'Productos de tienda'

    @property
    def valor_inventario(self):
        return self.costo_unitario * self.stock

    @property
    def bajo_stock(self):
        return self.stock <= self.stock_minimo

    def save(self, *args, **kwargs):
        if self.referencia == '':
            self.referencia = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class MovimientoTienda(models.Model):
    class Tipos(models.TextChoices):
        INGRESO = 'INGRESO', 'Ingreso'
        EGRESO = 'EGRESO', 'Egreso'

    class Origenes(models.TextChoices):
        VENTA = 'VENTA', 'Venta'
        COMPRA = 'COMPRA', 'Compra de producto'
        GASTO = 'GASTO', 'Gasto general'

    cuenta = models.ForeignKey(
        CuentaTienda,
        on_delete=models.PROTECT,
        related_name='movimientos',
    )
    tipo = models.CharField(max_length=10, choices=Tipos.choices)
    origen = models.CharField(max_length=10, choices=Origenes.choices)
    concepto = models.CharField(max_length=200)
    valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    producto = models.ForeignKey(
        ProductoTienda,
        on_delete=models.PROTECT,
        related_name='movimientos',
        null=True,
        blank=True,
    )
    cantidad = models.PositiveIntegerField(null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_tienda_registrados',
    )

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name = 'Movimiento de tienda'
        verbose_name_plural = 'Movimientos de tienda'

    def __str__(self):
        return f'{self.get_origen_display()} - {self.concepto} - {self.valor}'


class AjusteInventario(models.Model):
    class Tipos(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada'
        SALIDA = 'SALIDA', 'Salida'

    producto = models.ForeignKey(
        ProductoTienda,
        on_delete=models.PROTECT,
        related_name='ajustes_inventario',
    )
    tipo = models.CharField(max_length=10, choices=Tipos.choices)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    stock_anterior = models.PositiveIntegerField()
    stock_nuevo = models.PositiveIntegerField()
    motivo = models.CharField(max_length=200)
    fecha = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ajustes_tienda_registrados',
    )

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name = 'Ajuste de inventario'
        verbose_name_plural = 'Ajustes de inventario'

    def __str__(self):
        return f'{self.producto} - {self.tipo} {self.cantidad}'
