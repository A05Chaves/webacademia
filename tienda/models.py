from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Monedas(models.TextChoices):
    COP = 'COP', 'Pesos colombianos (COP)'
    USD = 'USD', 'Dólares (USD)'


class CategoriaProducto(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Categoría de producto'
        verbose_name_plural = 'Categorías de producto'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class SubcategoriaProducto(models.Model):
    categoria = models.ForeignKey(
        CategoriaProducto, on_delete=models.PROTECT, related_name='subcategorias'
    )
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['categoria__nombre', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['categoria', 'nombre'], name='subcategoria_unica_por_categoria'
            ),
        ]
        verbose_name = 'Subcategoría de producto'
        verbose_name_plural = 'Subcategorías de producto'

    def __str__(self):
        return f'{self.categoria.nombre} / {self.nombre}'


class CuentaTienda(models.Model):
    class Tipos(models.TextChoices):
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        BANCO = 'BANCO', 'Banco'
        BILLETERA = 'BILLETERA', 'Billetera digital'
        OTRO = 'OTRO', 'Otro'

    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=Tipos.choices)
    moneda = models.CharField(
        max_length=3, choices=Monedas.choices, default=Monedas.COP)
    saldo_inicial = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    fecha_saldo_inicial = models.DateField(default=timezone.localdate)
    activa = models.BooleanField(default=True)
    fecha_inactivacion = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['moneda', '-activa', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['nombre', 'moneda'], name='cuenta_tienda_nombre_moneda_unicos'
            ),
        ]
        verbose_name = 'Cuenta de tienda'
        verbose_name_plural = 'Cuentas de tienda'

    @property
    def saldo_actual(self):
        movimientos = self.movimientos.filter(
            fecha__date__gte=self.fecha_saldo_inicial)
        ingresos = movimientos.filter(tipo=MovimientoTienda.Tipos.INGRESO).aggregate(
            total=models.Sum('valor')
        )['total'] or Decimal('0')
        egresos = movimientos.filter(tipo=MovimientoTienda.Tipos.EGRESO).aggregate(
            total=models.Sum('valor')
        )['total'] or Decimal('0')
        return self.saldo_inicial + ingresos - egresos

    def save(self, *args, **kwargs):
        if self.activa:
            self.fecha_inactivacion = None
        elif not self.fecha_inactivacion:
            self.fecha_inactivacion = timezone.localdate()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.nombre} ({self.moneda})'


class ClienteTienda(models.Model):
    class TiposDocumento(models.TextChoices):
        CC = 'CC', 'Cédula de ciudadanía'
        CE = 'CE', 'Cédula de extranjería'
        NIT = 'NIT', 'NIT'
        PAS = 'PAS', 'Pasaporte'
        TI = 'TI', 'Tarjeta de identidad'
        OTRO = 'OTRO', 'Otro'

    nombres = models.CharField(max_length=150)
    tipo_documento = models.CharField(
        max_length=10, choices=TiposDocumento.choices)
    numero_documento = models.CharField(max_length=30, unique=True)
    telefono_whatsapp = models.CharField(max_length=20, blank=True)
    correo = models.EmailField(blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    acepta_whatsapp = models.BooleanField(
        default=False,
        help_text='El cliente autorizó recibir comprobantes y recordatorios por WhatsApp.',
    )
    preferencial = models.BooleanField(default=False)
    descuento_preferencial = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombres']
        verbose_name = 'Cliente de tienda'
        verbose_name_plural = 'Clientes de tienda'

    def __str__(self):
        return f'{self.nombres} - {self.numero_documento}'


class ProductoTienda(models.Model):
    class Publicos(models.TextChoices):
        ADULTO = 'ADULTO', 'Adulto'
        NINO = 'NINO', 'Niño'
        TODOS = 'TODOS', 'Todos'

    class Generos(models.TextChoices):
        HOMBRE = 'HOMBRE', 'Hombre'
        MUJER = 'MUJER', 'Mujer'
        UNISEX = 'UNISEX', 'Unisex'

    categoria = models.ForeignKey(
        CategoriaProducto, on_delete=models.PROTECT, related_name='productos',
        null=True, blank=True,
    )
    subcategoria = models.ForeignKey(
        SubcategoriaProducto, on_delete=models.PROTECT, related_name='productos',
        null=True, blank=True,
    )
    codigo_producto = models.CharField(
        max_length=60, blank=True,
        help_text='(Código maestro)',
    )
    nombre = models.CharField(max_length=150)
    referencia = models.CharField(
        max_length=60, unique=True, null=True, blank=True,
        help_text='SKU único de esta variante.',
    )
    codigo_barras = models.CharField(
        max_length=80, unique=True, null=True, blank=True)
    descripcion = models.TextField(blank=True)
    marca = models.CharField(max_length=100, blank=True)
    linea_modelo = models.CharField(max_length=100, blank=True)
    disciplina = models.CharField(max_length=80, blank=True)
    publico = models.CharField(
        max_length=10, choices=Publicos.choices, blank=True)
    genero = models.CharField(
        max_length=10, choices=Generos.choices, blank=True)
    color = models.CharField(max_length=50, blank=True)
    talla = models.CharField(max_length=30, blank=True)
    unidad = models.CharField(max_length=30, default='Unidad')
    material = models.CharField(max_length=120, blank=True)
    peso = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True)
    url_imagen = models.URLField(blank=True)
    ubicacion = models.CharField(max_length=100, blank=True)
    proveedor = models.CharField(max_length=150, blank=True)
    codigo_proveedor = models.CharField(max_length=60, blank=True)
    moneda = models.CharField(
        max_length=3, choices=Monedas.choices, default=Monedas.COP)
    precio_venta = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    costo_unitario = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    stock = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    fecha_inactivacion = models.DateField(null=True, blank=True)
    motivo_inactivacion = models.CharField(max_length=200, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activo', 'nombre', 'color', 'talla']
        verbose_name = 'Producto de tienda'
        verbose_name_plural = 'Productos de tienda'

    @property
    def valor_inventario(self):
        return self.costo_unitario * self.stock

    @property
    def bajo_stock(self):
        return self.stock <= self.stock_minimo

    @property
    def nombre_variante(self):
        atributos = [valor for valor in (self.color, self.talla) if valor]
        return f'{self.nombre} - {" / ".join(atributos)}' if atributos else self.nombre

    def clean(self):
        if self.subcategoria and self.categoria_id != self.subcategoria.categoria_id:
            raise ValidationError(
                {'subcategoria': 'La subcategoría no pertenece a la categoría.'})

    def save(self, *args, **kwargs):
        self.referencia = self.referencia or None
        self.codigo_barras = self.codigo_barras or None
        if self.activo:
            self.fecha_inactivacion = None
            self.motivo_inactivacion = ''
        elif not self.fecha_inactivacion:
            self.fecha_inactivacion = timezone.localdate()
        super().save(*args, **kwargs)

    def __str__(self):
        sku = f' [{self.referencia}]' if self.referencia else ''
        return f'{self.nombre_variante}{sku}'


class VentaTienda(models.Model):
    class Modalidades(models.TextChoices):
        CONTADO = 'CONTADO', 'Contado'
        CREDITO = 'CREDITO', 'Crédito'

    class Estados(models.TextChoices):
        PAGADA = 'PAGADA', 'Pagada'
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        PARCIAL = 'PARCIAL', 'Pago parcial'
        ANULADA = 'ANULADA', 'Anulada'

    numero = models.CharField(max_length=24, unique=True, blank=True)
    cliente = models.ForeignKey(
        ClienteTienda, on_delete=models.PROTECT, related_name='ventas',
        null=True, blank=True,
    )
    modalidad = models.CharField(max_length=10, choices=Modalidades.choices)
    estado = models.CharField(max_length=12, choices=Estados.choices)
    moneda = models.CharField(max_length=3, choices=Monedas.choices)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    saldo_pendiente = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    fecha = models.DateTimeField(default=timezone.now)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    numero_cuotas = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    observaciones = models.TextField(blank=True)
    email_enviado_a = models.EmailField(blank=True)
    fecha_envio_correo = models.DateTimeField(null=True, blank=True)
    error_envio_correo = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ventas_tienda_registradas',
    )

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name = 'Venta de tienda'
        verbose_name_plural = 'Ventas de tienda'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.numero:
            self.numero = f'VT-{self.fecha:%Y%m}-{self.pk:06d}'
            super().save(update_fields=['numero'])

    @property
    def esta_vencida(self):
        if self.pk and self.cuotas.exists():
            return self.cuotas.filter(
                saldo__gt=0, fecha_vencimiento__lt=timezone.localdate()
            ).exists()
        return (
            self.saldo_pendiente > 0 and self.fecha_vencimiento
            and self.fecha_vencimiento < timezone.localdate()
        )

    @property
    def proximo_vencimiento(self):
        cuota = self.cuotas.filter(saldo__gt=0).order_by(
            'fecha_vencimiento', 'numero').first()
        return cuota.fecha_vencimiento if cuota else None

    @property
    def cuotas_pagadas(self):
        return self.cuotas.filter(estado=CuotaVentaTienda.Estados.PAGADA).count()

    @property
    def progreso_cuotas(self):
        return f'{self.cuotas_pagadas}/{self.numero_cuotas}'

    def actualizar_saldo(self):
        pagado = self.movimientos.filter(
            tipo=MovimientoTienda.Tipos.INGRESO
        ).aggregate(total=models.Sum('valor'))['total'] or Decimal('0')
        self.saldo_pendiente = max(self.total - pagado, Decimal('0'))
        if self.saldo_pendiente == 0:
            self.estado = self.Estados.PAGADA
        elif pagado:
            self.estado = self.Estados.PARCIAL
        else:
            self.estado = self.Estados.PENDIENTE
        self.save(update_fields=['saldo_pendiente', 'estado'])

    def __str__(self):
        return self.numero or f'Venta {self.pk}'


class DetalleVentaTienda(models.Model):
    venta = models.ForeignKey(
        VentaTienda, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(
        ProductoTienda, on_delete=models.PROTECT, related_name='detalles_venta'
    )
    descripcion = models.CharField(max_length=220)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = 'Detalle de venta de tienda'
        verbose_name_plural = 'Detalles de venta de tienda'


class CuotaVentaTienda(models.Model):
    class Estados(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        PARCIAL = 'PARCIAL', 'Pago parcial'
        PAGADA = 'PAGADA', 'Pagada'

    venta = models.ForeignKey(
        VentaTienda, on_delete=models.CASCADE, related_name='cuotas')
    numero = models.PositiveSmallIntegerField()
    fecha_vencimiento = models.DateField()
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    saldo = models.DecimalField(max_digits=14, decimal_places=2)
    estado = models.CharField(
        max_length=10, choices=Estados.choices, default=Estados.PENDIENTE
    )

    class Meta:
        ordering = ['fecha_vencimiento', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['venta', 'numero'], name='numero_cuota_unico_por_venta'
            ),
        ]
        verbose_name = 'Cuota de venta'
        verbose_name_plural = 'Cuotas de venta'

    @property
    def esta_vencida(self):
        return self.saldo > 0 and self.fecha_vencimiento < timezone.localdate()

    def __str__(self):
        return f'{self.venta.numero} - cuota {self.numero}'


class MovimientoTienda(models.Model):
    class Tipos(models.TextChoices):
        INGRESO = 'INGRESO', 'Ingreso'
        EGRESO = 'EGRESO', 'Egreso'

    class Origenes(models.TextChoices):
        VENTA = 'VENTA', 'Venta de contado'
        ABONO = 'ABONO', 'Abono de venta a crédito'
        COMPRA = 'COMPRA', 'Compra de producto'
        GASTO = 'GASTO', 'Gasto general'

    cuenta = models.ForeignKey(
        CuentaTienda, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=10, choices=Tipos.choices)
    origen = models.CharField(max_length=10, choices=Origenes.choices)
    concepto = models.CharField(max_length=200)
    valor = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    moneda = models.CharField(
        max_length=3, choices=Monedas.choices, default=Monedas.COP)
    producto = models.ForeignKey(
        ProductoTienda, on_delete=models.PROTECT, related_name='movimientos',
        null=True, blank=True,
    )
    venta = models.ForeignKey(
        VentaTienda, on_delete=models.PROTECT, related_name='movimientos',
        null=True, blank=True,
    )
    cantidad = models.PositiveIntegerField(null=True, blank=True)
    costo_unitario = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movimientos_tienda_registrados',
    )

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name = 'Movimiento de tienda'
        verbose_name_plural = 'Movimientos de tienda'

    def clean(self):
        if self.cuenta_id and self.moneda != self.cuenta.moneda:
            raise ValidationError(
                {'cuenta': 'La moneda del movimiento debe coincidir con la cuenta.'})
        if self.venta_id and self.moneda != self.venta.moneda:
            raise ValidationError(
                {'venta': 'La moneda del abono debe coincidir con la venta.'})

    def save(self, *args, **kwargs):
        if self.cuenta_id:
            self.moneda = self.cuenta.moneda
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_origen_display()} - {self.concepto} - {self.valor} {self.moneda}'


class AplicacionAbonoCuota(models.Model):
    movimiento = models.ForeignKey(
        MovimientoTienda, on_delete=models.CASCADE, related_name='aplicaciones_cuotas'
    )
    cuota = models.ForeignKey(
        CuotaVentaTienda, on_delete=models.PROTECT, related_name='aplicaciones'
    )
    valor = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)]
    )

    class Meta:
        verbose_name = 'Aplicación de abono a cuota'
        verbose_name_plural = 'Aplicaciones de abonos a cuotas'


class AjusteInventario(models.Model):
    class Tipos(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada'
        SALIDA = 'SALIDA', 'Salida'

    producto = models.ForeignKey(
        ProductoTienda, on_delete=models.PROTECT, related_name='ajustes_inventario'
    )
    tipo = models.CharField(max_length=10, choices=Tipos.choices)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    stock_anterior = models.PositiveIntegerField()
    stock_nuevo = models.PositiveIntegerField()
    costo_unitario = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    motivo = models.CharField(max_length=200)
    fecha = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ajustes_tienda_registrados',
    )

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name = 'Ajuste de inventario'
        verbose_name_plural = 'Ajustes de inventario'

    def __str__(self):
        return f'{self.producto} - {self.tipo} {self.cantidad}'
