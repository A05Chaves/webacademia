from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.formats import number_format

from alumnos.models import Alumno
from config.file_validation import validate_image

from .models import (
    AjusteInventario,
    CategoriaMovimientoTienda,
    CategoriaProducto,
    ClienteTienda,
    CompraProveedorTienda,
    CuentaTienda,
    CuotaVentaTienda,
    CuotaCompraTienda,
    Monedas,
    PedidoTienda,
    DisciplinaProducto,
    LineaModeloProducto,
    MarcaProducto,
    ProductoTienda,
    ProveedorTienda,
    SubcategoriaProducto,
    VentaTienda,
)


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            else:
                css = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
                field.widget.attrs.setdefault('class', css)


class CompradorTiendaField(forms.Field):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('label', 'Comprador')
        kwargs.setdefault(
            'help_text',
            'Incluye estudiantes de la academia y clientes externos registrados.',
        )
        kwargs.setdefault('widget', forms.Select(attrs={'class': 'form-select'}))
        super().__init__(*args, **kwargs)
        self.widget.choices = [('', '---------')]

    def actualizar_opciones(self):
        alumnos = Alumno.objects.select_related('user').order_by(
            'user__first_name', 'user__last_name', 'documento'
        )
        documentos_alumnos = alumnos.values_list('documento', flat=True)
        clientes = ClienteTienda.objects.filter(activo=True).exclude(
            numero_documento__in=documentos_alumnos
        ).order_by('nombres')
        self.widget.choices = [
            ('', '---------'),
            (
                'Estudiantes de la academia',
                [
                    (f'alumno:{alumno.pk}', f'{alumno} — {alumno.documento}')
                    for alumno in alumnos
                ],
            ),
            (
                'Clientes externos',
                [
                    (
                        f'cliente:{cliente.pk}',
                        f'{cliente.nombres} — {cliente.numero_documento}',
                    )
                    for cliente in clientes
                ],
            ),
        ]

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return None
        try:
            tipo, identificador = (
                value.split(':', 1) if ':' in value else ('cliente', value)
            )
            if tipo == 'alumno':
                return Alumno.objects.select_related('user').get(pk=identificador)
            if tipo == 'cliente':
                return ClienteTienda.objects.get(pk=identificador, activo=True)
        except (Alumno.DoesNotExist, ClienteTienda.DoesNotExist, ValueError):
            pass
        raise forms.ValidationError('El comprador seleccionado ya no está disponible.')


class CuentaTiendaForm(BootstrapModelForm):
    class Meta:
        model = CuentaTienda
        fields = [
            'nombre', 'tipo', 'moneda', 'saldo_inicial',
            'fecha_saldo_inicial', 'activa',
        ]
        widgets = {'fecha_saldo_inicial': forms.DateInput(attrs={'type': 'date'})}


class CategoriaMovimientoTiendaForm(BootstrapModelForm):
    class Meta:
        model = CategoriaMovimientoTienda
        fields = ['nombre', 'tipo', 'naturaleza', 'descripcion', 'activa']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.movimientos.exists():
            for campo in ('tipo', 'naturaleza'):
                self.fields[campo].disabled = True
            self.fields['naturaleza'].help_text = (
                'La naturaleza no puede cambiar porque esta categoría ya tiene historial.'
            )

    def clean_nombre(self):
        return self.cleaned_data['nombre'].strip().upper()


class CategoriaProductoForm(BootstrapModelForm):
    class Meta:
        model = CategoriaProducto
        fields = ['codigo', 'nombre', 'activa']


class SubcategoriaProductoForm(BootstrapModelForm):
    class Meta:
        model = SubcategoriaProducto
        fields = ['categoria', 'codigo', 'nombre', 'activa']


class MarcaProductoForm(BootstrapModelForm):
    class Meta:
        model = MarcaProducto
        fields = ['nombre', 'activa']


class LineaModeloProductoForm(BootstrapModelForm):
    class Meta:
        model = LineaModeloProducto
        fields = ['marca', 'nombre', 'activa']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        marcas = MarcaProducto.objects.filter(activa=True)
        if self.instance.pk:
            marcas = MarcaProducto.objects.filter(
                Q(activa=True) | Q(pk=self.instance.marca_id)
            )
        self.fields['marca'].queryset = marcas


class DisciplinaProductoForm(BootstrapModelForm):
    class Meta:
        model = DisciplinaProducto
        fields = ['nombre', 'activa']


class ProveedorTiendaForm(BootstrapModelForm):
    class Meta:
        model = ProveedorTienda
        fields = ['codigo', 'nombre', 'contacto', 'telefono', 'correo', 'activo']

    def clean_codigo(self):
        return self.cleaned_data['codigo'].strip().upper()

    def clean_nombre(self):
        return self.cleaned_data['nombre'].strip().title()


class ClienteTiendaForm(BootstrapModelForm):
    class Meta:
        model = ClienteTienda
        fields = [
            'nombres', 'tipo_documento', 'numero_documento',
            'telefono_whatsapp', 'correo', 'direccion', 'acepta_whatsapp',
            'preferencial', 'descuento_preferencial', 'activo',
        ]


class ProductoTiendaForm(BootstrapModelForm):
    class ProveedorPorNombreField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            return obj.nombre

    class ProveedorPorCodigoField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            return obj.codigo

    proveedor_catalogo = ProveedorPorNombreField(
        queryset=ProveedorTienda.objects.none(),
        required=False,
        label='Proveedor',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    codigo_proveedor_seleccionado = ProveedorPorCodigoField(
        queryset=ProveedorTienda.objects.none(),
        required=False,
        label='Código del proveedor',
        help_text='Al seleccionar el proveedor o su código, el otro campo se completa automáticamente.',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    stock_inicial = forms.IntegerField(
        min_value=0, initial=0, required=False, label='Inventario inicial',
        help_text='Después se modifica mediante compras, ventas o ajustes.',
    )

    class Meta:
        model = ProductoTienda
        fields = [
            'categoria', 'subcategoria', 'codigo_producto', 'nombre', 'referencia',
            'codigo_barras', 'marca', 'linea_modelo', 'descripcion', 'disciplina',
            'publico', 'genero', 'color', 'talla', 'unidad', 'material', 'peso',
            'imagen', 'url_imagen', 'ubicacion', 'proveedor_catalogo',
            'codigo_proveedor_seleccionado', 'moneda',
            'costo_unitario', 'precio_venta', 'stock_minimo', 'activo',
            'disponible_sobre_pedido',
            'motivo_inactivacion',
        ]
        widgets = {'descripcion': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['moneda'].required = False
        self.fields['moneda'].initial = 'COP'
        self.fields['unidad'].required = False
        self.fields['unidad'].initial = 'Unidad'
        categoria_id = None
        if self.is_bound:
            categoria_id = self.data.get(self.add_prefix('categoria'))
        elif self.instance.pk:
            categoria_id = self.instance.categoria_id
        subcategorias = SubcategoriaProducto.objects.none()
        if str(categoria_id or '').isdigit():
            subcategorias = SubcategoriaProducto.objects.filter(
                categoria_id=categoria_id, activa=True
            )
            if self.instance.pk and self.instance.subcategoria_id:
                subcategorias = SubcategoriaProducto.objects.filter(
                    Q(categoria_id=categoria_id, activa=True)
                    | Q(pk=self.instance.subcategoria_id)
                )
        self.fields['subcategoria'].queryset = subcategorias
        filtros_actuales = {
            'marca': self.instance.marca_id if self.instance.pk else None,
            'linea_modelo': self.instance.linea_modelo_id if self.instance.pk else None,
            'disciplina': self.instance.disciplina_id if self.instance.pk else None,
        }
        modelos_catalogo = {
            'marca': MarcaProducto,
            'linea_modelo': LineaModeloProducto,
            'disciplina': DisciplinaProducto,
        }
        for campo, modelo in modelos_catalogo.items():
            actual = filtros_actuales[campo]
            consulta = modelo.objects.filter(activa=True)
            if actual:
                consulta = modelo.objects.filter(Q(activa=True) | Q(pk=actual))
            self.fields[campo].queryset = consulta
        proveedor_actual = (
            self.instance.proveedor_catalogo_id if self.instance.pk else None
        )
        proveedores = ProveedorTienda.objects.filter(activo=True)
        if proveedor_actual:
            proveedores = ProveedorTienda.objects.filter(
                Q(activo=True) | Q(pk=proveedor_actual)
            )
        self.fields['proveedor_catalogo'].queryset = proveedores
        self.fields['codigo_proveedor_seleccionado'].queryset = proveedores
        if proveedor_actual:
            self.fields['codigo_proveedor_seleccionado'].initial = proveedor_actual
        if self.instance and self.instance.pk:
            self.fields.pop('stock_inicial')

    def clean_moneda(self):
        return self.cleaned_data.get('moneda') or 'COP'

    def clean_unidad(self):
        return self.cleaned_data.get('unidad') or 'Unidad'

    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        if imagen and hasattr(imagen, 'content_type'):
            validate_image(imagen)
        return imagen

    def clean(self):
        cleaned = super().clean()
        categoria = cleaned.get('categoria')
        subcategoria = cleaned.get('subcategoria')
        if subcategoria and subcategoria.categoria_id != getattr(categoria, 'id', None):
            self.add_error('subcategoria', 'La subcategoría no pertenece a la categoría seleccionada.')
        por_nombre = cleaned.get('proveedor_catalogo')
        por_codigo = cleaned.get('codigo_proveedor_seleccionado')
        if por_nombre and por_codigo and por_nombre.pk != por_codigo.pk:
            self.add_error(
                'codigo_proveedor_seleccionado',
                'El código no corresponde al proveedor seleccionado.',
            )
        cleaned['proveedor_seleccionado'] = por_nombre or por_codigo
        return cleaned

    def save(self, commit=True):
        producto = super().save(commit=False)
        proveedor = self.cleaned_data.get('proveedor_seleccionado')
        producto.proveedor_catalogo = proveedor
        producto.proveedor = proveedor.nombre if proveedor else ''
        producto.codigo_proveedor = proveedor.codigo if proveedor else ''
        if commit:
            producto.save()
            self.save_m2m()
        return producto


class OperacionProductoForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=ProductoTienda.objects.none(), widget=forms.Select(attrs={'class': 'form-select'})
    )
    cantidad = forms.IntegerField(
        min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )
    cuenta = forms.ModelChoiceField(
        queryset=CuentaTienda.objects.none(), widget=forms.Select(attrs={'class': 'form-select'})
    )
    observaciones = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta'].queryset = CuentaTienda.objects.filter(activa=True)

    def clean(self):
        cleaned = super().clean()
        producto, cuenta = cleaned.get('producto'), cleaned.get('cuenta')
        if producto and cuenta and producto.moneda != cuenta.moneda:
            raise forms.ValidationError(
                f'El producto está en {producto.moneda}; seleccione una cuenta en esa moneda.'
            )
        return cleaned


class VentaTiendaForm(OperacionProductoForm):
    fecha_venta = forms.DateField(
        required=False,
        label='Fecha de la venta',
        help_text='Opcional. Si la deja vacía se usará automáticamente la fecha de hoy.',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    moneda = forms.ChoiceField(
        choices=Monedas.choices, initial=Monedas.COP, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    modalidad = forms.ChoiceField(
        choices=VentaTienda.Modalidades.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    cliente = CompradorTiendaField(
        help_text=(
            'Seleccione un estudiante de la academia o un cliente externo. '
            'Es obligatorio para ventas a crédito y para emitir paz y salvo.'
        ),
    )
    descuento_porcentaje = forms.DecimalField(
        min_value=0, max_value=100, decimal_places=2, initial=0, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'step': '0.01'}),
    )
    fecha_vencimiento = forms.DateField(
        label='Vencimiento de la primera cuota',
        required=False, widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    numero_cuotas = forms.IntegerField(
        label='Número de cuotas', min_value=1, max_value=60, initial=1, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 60}),
    )
    tipo_entrega = forms.ChoiceField(
        label='Entrega', choices=VentaTienda.TiposEntrega.choices,
        initial=VentaTienda.TiposEntrega.INMEDIATA, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    fecha_entrega_estimada = forms.DateField(
        required=False, label='Fecha estimada de entrega',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    registrar_comprador = forms.BooleanField(
        required=False, label='Registrar un comprador nuevo en esta venta',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    comprador_nombres = forms.CharField(
        required=False, max_length=150, label='Nombre completo',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    comprador_tipo_documento = forms.ChoiceField(
        required=False, label='Tipo de documento', choices=ClienteTienda.TiposDocumento.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    comprador_numero_documento = forms.CharField(
        required=False, max_length=30, label='Número de documento',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    comprador_whatsapp = forms.CharField(
        required=False, max_length=20, label='WhatsApp',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 573001234567'}),
    )
    comprador_correo = forms.EmailField(
        required=False, label='Correo electrónico',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    comprador_direccion = forms.CharField(
        required=False, max_length=200, label='Dirección',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    comprador_acepta_whatsapp = forms.BooleanField(
        required=False, label='Autoriza comprobantes y recordatorios por WhatsApp',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].actualizar_opciones()
        self.fields['producto'].queryset = ProductoTienda.objects.filter(
            activo=True, precio_venta__gt=0
        )
        self.fields['cuenta'].required = False
        self.fields['modalidad'].required = False
        self.fields['modalidad'].initial = VentaTienda.Modalidades.CONTADO

    def clean(self):
        cleaned = super().clean()
        modalidad = cleaned.get('modalidad') or VentaTienda.Modalidades.CONTADO
        cleaned['modalidad'] = modalidad
        cliente = cleaned.get('cliente')
        registrar_comprador = cleaned.get('registrar_comprador')
        cuenta = cleaned.get('cuenta')
        producto = cleaned.get('producto')
        vencimiento = cleaned.get('fecha_vencimiento')
        moneda = cleaned.get('moneda') or getattr(producto, 'moneda', Monedas.COP)
        cleaned['moneda'] = moneda
        tipo_entrega = cleaned.get('tipo_entrega') or VentaTienda.TiposEntrega.INMEDIATA
        cleaned['tipo_entrega'] = tipo_entrega
        fecha_entrega = cleaned.get('fecha_entrega_estimada')
        if producto and moneda and producto.moneda != moneda:
            self.add_error('producto', f'Seleccione un producto configurado en {moneda}.')
        if tipo_entrega == VentaTienda.TiposEntrega.SOBRE_PEDIDO:
            if not fecha_entrega:
                self.add_error('fecha_entrega_estimada', 'Indique la fecha estimada de entrega.')
            elif fecha_entrega < timezone.localdate():
                self.add_error('fecha_entrega_estimada', 'La entrega no puede quedar en una fecha pasada.')
        else:
            cleaned['fecha_entrega_estimada'] = None
        if modalidad == VentaTienda.Modalidades.CREDITO:
            if not cliente and not registrar_comprador:
                self.add_error('cliente', 'Seleccione un comprador o regístrelo dentro de esta venta.')
            if not vencimiento:
                self.add_error('fecha_vencimiento', 'Indique cuándo vence el crédito.')
            elif vencimiento < timezone.localdate():
                self.add_error('fecha_vencimiento', 'La fecha de vencimiento no puede estar vencida.')
        elif not cuenta:
            self.add_error('cuenta', 'Seleccione la cuenta que recibe el pago.')
        if registrar_comprador:
            for campo in ('comprador_nombres', 'comprador_tipo_documento', 'comprador_numero_documento'):
                if not cleaned.get(campo):
                    self.add_error(campo, 'Este dato es obligatorio para registrar al comprador.')
            documento = cleaned.get('comprador_numero_documento')
            if documento and ClienteTienda.objects.filter(numero_documento=documento).exists():
                self.add_error(
                    'comprador_numero_documento',
                    'Este documento ya existe. Seleccione el comprador registrado.',
                )
        if modalidad != VentaTienda.Modalidades.CREDITO:
            cleaned['numero_cuotas'] = 1
            cleaned['fecha_vencimiento'] = None
        elif not cleaned.get('numero_cuotas'):
            cleaned['numero_cuotas'] = 1
        if cuenta and producto and cuenta.moneda != producto.moneda:
            self.add_error('cuenta', f'Seleccione una cuenta en {producto.moneda}.')
        return cleaned


class CarteraInicialTiendaForm(forms.Form):
    cliente = CompradorTiendaField(
        label='Comprador registrado o estudiante',
        help_text='Seleccione el deudor si pertenece a la academia o ya existe como cliente.',
    )
    registrar_comprador = forms.BooleanField(
        required=False,
        label='El comprador todavía no está registrado',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    comprador_nombres = forms.CharField(
        required=False, max_length=150, label='Nombre completo',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    comprador_tipo_documento = forms.ChoiceField(
        required=False, label='Tipo de documento',
        choices=ClienteTienda.TiposDocumento.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    comprador_numero_documento = forms.CharField(
        required=False, max_length=30, label='Número de documento',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    comprador_whatsapp = forms.CharField(
        required=False, max_length=20, label='WhatsApp',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Ej. 573001234567',
        }),
    )
    comprador_correo = forms.EmailField(
        required=False, label='Correo electrónico',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    comprador_direccion = forms.CharField(
        required=False, max_length=200, label='Dirección',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    moneda = forms.ChoiceField(
        choices=Monedas.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    saldo_inicial = forms.DecimalField(
        label='Saldo pendiente a incorporar',
        min_value=Decimal('0.01'), max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'min': '0.01', 'step': '0.01',
        }),
        help_text='Ingrese únicamente lo que aún debe el comprador, no el valor original si ya hizo pagos.',
    )
    fecha_origen = forms.DateField(
        label='Fecha de la deuda original', initial=timezone.localdate,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    fecha_vencimiento = forms.DateField(
        label='Vencimiento de la primera cuota', initial=timezone.localdate,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text='Puede ser una fecha pasada si la deuda ya está vencida.',
    )
    numero_cuotas = forms.IntegerField(
        label='Número de cuotas pendientes', min_value=1, max_value=60, initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'min': 1, 'max': 60,
        }),
    )
    referencia_externa = forms.CharField(
        required=False, max_length=80,
        label='Factura o referencia anterior',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text='Puede anotar el origen de la deuda o acuerdos previos con el comprador.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].actualizar_opciones()

    def clean_fecha_origen(self):
        fecha = self.cleaned_data['fecha_origen']
        if fecha > timezone.localdate():
            raise forms.ValidationError('La fecha de la deuda no puede ser futura.')
        return fecha

    def clean(self):
        cleaned = super().clean()
        cliente = cleaned.get('cliente')
        registrar = cleaned.get('registrar_comprador')
        if cliente and registrar:
            self.add_error(
                'registrar_comprador',
                'Use el comprador seleccionado o registre uno nuevo, pero no ambos.',
            )
        elif not cliente and not registrar:
            self.add_error(
                'cliente', 'Seleccione el comprador o registre uno nuevo aquí mismo.'
            )
        if registrar:
            for campo in (
                'comprador_nombres', 'comprador_tipo_documento',
                'comprador_numero_documento',
            ):
                if not cleaned.get(campo):
                    self.add_error(campo, 'Este dato es obligatorio para registrar al comprador.')
            documento = cleaned.get('comprador_numero_documento')
            if documento and ClienteTienda.objects.filter(
                numero_documento=documento
            ).exists():
                self.add_error(
                    'comprador_numero_documento',
                    'Este documento ya existe. Seleccione el comprador registrado.',
                )
        return cleaned


class CompraTiendaForm(OperacionProductoForm):
    proveedor = forms.ModelChoiceField(
        queryset=ProveedorTienda.objects.none(), required=False,
        label='Proveedor de la factura',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text=(
            'Proveedor de la factura. Si todos los productos tienen el mismo proveedor, '
            'se completa automáticamente.'
        ),
    )
    costo_unitario = forms.DecimalField(
        min_value=Decimal('0.01'), max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
        help_text='Costo real pagado por unidad en esta compra.',
    )
    modalidad = forms.ChoiceField(
        choices=CompraProveedorTienda.Modalidades.choices,
        initial=CompraProveedorTienda.Modalidades.CONTADO, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    abono_inicial = forms.DecimalField(
        label='Abono inicial', required=False, initial=0, min_value=0,
        max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
    )
    fecha_vencimiento = forms.DateField(
        label='Vencimiento de la primera cuota', required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    numero_cuotas = forms.IntegerField(
        label='Número de cuotas', required=False, initial=1, min_value=1, max_value=60,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 60}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = ProductoTienda.objects.filter(activo=True)
        self.fields['proveedor'].queryset = ProveedorTienda.objects.filter(activo=True)
        self.fields['cuenta'].required = False

    def clean(self):
        cleaned = super().clean()
        ids = self.data.getlist('producto') if self.is_bound else []
        cantidades = self.data.getlist('cantidad') if self.is_bound else []
        costos = self.data.getlist('costo_unitario') if self.is_bound else []
        lineas = []
        if not ids or not (len(ids) == len(cantidades) == len(costos)):
            self.add_error(
                None,
                'Agregue al menos un producto y complete todos los renglones de la compra.',
            )
        else:
            productos = {
                str(producto.pk): producto
                for producto in self.fields['producto'].queryset.filter(pk__in=ids)
            }
            usados = set()
            campo_cantidad = forms.IntegerField(min_value=1)
            campo_costo = forms.DecimalField(
                min_value=Decimal('0.01'), max_digits=14, decimal_places=2
            )
            for indice, (producto_id, cantidad_raw, costo_raw) in enumerate(
                zip(ids, cantidades, costos), start=1
            ):
                producto = productos.get(producto_id)
                if not producto:
                    self.add_error(None, f'El producto del renglón {indice} no está disponible.')
                    continue
                if producto.pk in usados:
                    self.add_error(None, f'{producto.nombre_variante} está repetido en la compra.')
                    continue
                usados.add(producto.pk)
                try:
                    cantidad = campo_cantidad.clean(cantidad_raw)
                    costo = campo_costo.clean(costo_raw)
                except forms.ValidationError:
                    self.add_error(
                        None, f'Revise la cantidad y el costo del renglón {indice}.'
                    )
                    continue
                lineas.append({
                    'producto': producto,
                    'cantidad': cantidad,
                    'costo_unitario': costo,
                    'total': costo * cantidad,
                })
        monedas = {linea['producto'].moneda for linea in lineas}
        if len(monedas) > 1:
            self.add_error(None, 'Una misma factura no puede mezclar productos en COP y USD.')
        producto = lineas[0]['producto'] if lineas else cleaned.get('producto')
        modalidad = cleaned.get('modalidad') or CompraProveedorTienda.Modalidades.CONTADO
        cleaned['modalidad'] = modalidad
        abono = cleaned.get('abono_inicial') or Decimal('0')
        total = sum((linea['total'] for linea in lineas), Decimal('0'))
        cleaned['lineas_compra'] = lineas
        cleaned['total_compra'] = total
        if lineas:
            cleaned['producto'] = lineas[0]['producto']
            cleaned['cantidad'] = lineas[0]['cantidad']
            cleaned['costo_unitario'] = lineas[0]['costo_unitario']
        if not cleaned.get('proveedor') and lineas:
            proveedores_lineas = [
                linea['producto'].proveedor_catalogo_id for linea in lineas
            ]
            proveedores = set(proveedores_lineas)
            if all(proveedores_lineas) and len(proveedores) == 1:
                cleaned['proveedor'] = ProveedorTienda.objects.filter(
                    pk=proveedores.pop()
                ).first()
        cuenta = cleaned.get('cuenta')
        if abono > total:
            self.add_error('abono_inicial', 'El abono no puede superar el total de la compra.')
        if modalidad == CompraProveedorTienda.Modalidades.CONTADO:
            if not cuenta:
                self.add_error('cuenta', 'Seleccione la cuenta desde la que se pagó la compra.')
            cleaned['abono_inicial'] = total
            cleaned['numero_cuotas'] = 1
            cleaned['fecha_vencimiento'] = None
        else:
            if not cleaned.get('fecha_vencimiento'):
                self.add_error('fecha_vencimiento', 'Indique el vencimiento de la primera cuota.')
            elif cleaned['fecha_vencimiento'] < timezone.localdate():
                self.add_error('fecha_vencimiento', 'La fecha no puede estar vencida.')
            if not cleaned.get('numero_cuotas'):
                cleaned['numero_cuotas'] = 1
            if abono > 0 and not cuenta:
                self.add_error('cuenta', 'Seleccione la cuenta desde la que se hizo el abono.')
        moneda = next(iter(monedas), getattr(producto, 'moneda', None))
        if moneda and cleaned.get('cuenta') and moneda != cleaned['cuenta'].moneda:
            self.add_error('cuenta', f'Seleccione una cuenta en {moneda}.')
        return cleaned


class AbonoCompraForm(forms.Form):
    cuota = forms.ModelChoiceField(
        queryset=CuotaCompraTienda.objects.none(), label='Cuota que desea pagar',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    cuenta = forms.ModelChoiceField(
        queryset=CuentaTienda.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}),
    )
    valor = forms.DecimalField(
        min_value=Decimal('0.01'), max_digits=14, decimal_places=2,
        help_text='Puede pagar la cuota completa o hacer un abono diferente.',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
    )
    observaciones = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def __init__(self, *args, compra=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.compra = compra
        if compra:
            cuotas_pendientes = compra.cuotas.filter(saldo__gt=0).order_by(
                'fecha_vencimiento', 'numero'
            )
            self.fields['cuota'].queryset = cuotas_pendientes
            self.fields['cuota'].label_from_instance = (
                lambda cuota: f'Cuota {cuota.numero}'
            )
            self.fields['cuenta'].queryset = CuentaTienda.objects.filter(
                activa=True, moneda=compra.moneda
            )
            if not self.is_bound:
                primera_cuota = cuotas_pendientes.first()
                if primera_cuota:
                    self.initial['cuota'] = primera_cuota
                    self.initial['valor'] = primera_cuota.saldo

    def clean_valor(self):
        valor = self.cleaned_data['valor']
        if self.compra and valor > self.compra.saldo_pendiente:
            raise forms.ValidationError('El pago supera el saldo pendiente de la compra.')
        return valor


class PedidoTiendaForm(forms.ModelForm):
    class Meta:
        model = PedidoTienda
        fields = [
            'nombres', 'tipo_documento', 'numero_documento', 'telefono',
            'correo', 'modalidad_entrega', 'direccion', 'cuenta_pago',
            'referencia_pago', 'soporte_pago', 'observaciones_cliente',
        ]
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'tel'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'modalidad_entrega': forms.Select(attrs={'class': 'form-select'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'cuenta_pago': forms.Select(attrs={'class': 'form-select'}),
            'referencia_pago': forms.TextInput(attrs={'class': 'form-control'}),
            'soporte_pago': forms.ClearableFileInput(attrs={
                'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png,.webp',
            }),
            'observaciones_cliente': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, moneda=None, alumno=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.moneda = moneda
        self.fields['cuenta_pago'].queryset = CuentaTienda.objects.filter(
            activa=True, moneda=moneda
        ) if moneda else CuentaTienda.objects.none()
        if alumno and not self.is_bound:
            self.initial.update({
                'nombres': str(alumno),
                'numero_documento': alumno.documento,
                'telefono': alumno.user.telefono or alumno.telefono_acudiente or '',
                'correo': alumno.user.email or '',
                'direccion': alumno.direccion or '',
            })

    def clean_numero_documento(self):
        return ''.join(filter(str.isdigit, self.cleaned_data['numero_documento']))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('modalidad_entrega') != PedidoTienda.Entregas.ACADEMIA and not cleaned.get('direccion'):
            self.add_error('direccion', 'Indique la dirección para realizar la entrega o el envío.')
        cuenta = cleaned.get('cuenta_pago')
        if cuenta and self.moneda and cuenta.moneda != self.moneda:
            self.add_error('cuenta_pago', f'Seleccione una cuenta en {self.moneda}.')
        return cleaned


class GastoTiendaForm(forms.Form):
    cuenta = forms.ModelChoiceField(
        queryset=CuentaTienda.objects.none(), widget=forms.Select(attrs={'class': 'form-select'})
    )
    concepto = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    categoria = forms.ModelChoiceField(
        queryset=CategoriaMovimientoTienda.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    valor = forms.DecimalField(
        min_value=Decimal('0.01'), max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
    )
    fecha = forms.DateTimeField(
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M'],
    )
    observaciones = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    soporte = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png,.webp',
        }),
        help_text='Obligatorio para gastos no operacionales.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta'].queryset = CuentaTienda.objects.filter(activa=True)
        self.fields['categoria'].queryset = CategoriaMovimientoTienda.objects.filter(
            activa=True,
            tipo=CategoriaMovimientoTienda.Tipos.EGRESO,
        )

    def clean(self):
        cleaned = super().clean()
        categoria = cleaned.get('categoria')
        if (
            categoria
            and categoria.naturaleza
            == CategoriaMovimientoTienda.Naturalezas.NO_OPERACIONAL
            and not cleaned.get('soporte')
        ):
            self.add_error('soporte', 'Adjunta el soporte del gasto no operacional.')
        return cleaned


class IngresoTiendaForm(GastoTiendaForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = CategoriaMovimientoTienda.objects.filter(
            activa=True,
            tipo=CategoriaMovimientoTienda.Tipos.INGRESO,
        )
        self.fields['soporte'].help_text = (
            'Obligatorio para ingresos no operacionales.'
        )

    def clean(self):
        cleaned = forms.Form.clean(self)
        categoria = cleaned.get('categoria')
        if (
            categoria
            and categoria.naturaleza
            == CategoriaMovimientoTienda.Naturalezas.NO_OPERACIONAL
            and not cleaned.get('soporte')
        ):
            self.add_error('soporte', 'Adjunta el soporte del ingreso no operacional.')
        return cleaned


class TransferenciaTiendaForm(forms.Form):
    cuenta_origen = forms.ModelChoiceField(
        label='Cuenta de origen',
        queryset=CuentaTienda.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    cuenta_destino = forms.ModelChoiceField(
        label='Cuenta de destino',
        queryset=CuentaTienda.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    valor = forms.DecimalField(
        min_value=Decimal('0.01'),
        max_digits=14,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'min': '0.01', 'step': '0.01',
        }),
    )
    concepto = forms.CharField(
        max_length=160,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej. Traslado de efectivo a cuenta bancaria',
        }),
    )
    fecha = forms.DateTimeField(
        initial=timezone.now,
        widget=forms.DateTimeInput(
            attrs={'class': 'form-control', 'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cuentas_activas = CuentaTienda.objects.filter(activa=True)
        self.fields['cuenta_origen'].queryset = cuentas_activas
        self.fields['cuenta_destino'].queryset = cuentas_activas

    def clean(self):
        cleaned = super().clean()
        origen = cleaned.get('cuenta_origen')
        destino = cleaned.get('cuenta_destino')
        valor = cleaned.get('valor')
        if origen and destino:
            if origen == destino:
                self.add_error('cuenta_destino', 'La cuenta de destino debe ser diferente.')
            elif origen.moneda != destino.moneda:
                self.add_error(
                    'cuenta_destino',
                    'Las transferencias solo se permiten entre cuentas de la misma moneda.',
                )
        if origen and valor and valor > origen.saldo_actual:
            self.add_error(
                'valor',
                f'La cuenta de origen solo tiene {number_format(origen.saldo_actual, decimal_pos=2, force_grouping=True)} {origen.moneda}.',
            )
        return cleaned


class AbonoVentaForm(forms.Form):
    cuota = forms.ModelChoiceField(
        queryset=CuotaVentaTienda.objects.none(),
        required=False,
        label='Cuota que desea pagar',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='El pago se aplica primero a esta cuota; cualquier excedente abonará las demás.',
    )
    cuenta = forms.ModelChoiceField(
        queryset=CuentaTienda.objects.none(), widget=forms.Select(attrs={'class': 'form-select'})
    )
    valor = forms.DecimalField(
        min_value=Decimal('0.01'), max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    observaciones = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )

    def __init__(self, *args, venta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.venta = venta
        self.fields['cuenta'].queryset = CuentaTienda.objects.filter(
            activa=True, moneda=venta.moneda
        ) if venta else CuentaTienda.objects.none()
        cuotas_pendientes = venta.cuotas.filter(saldo__gt=0).order_by(
            'fecha_vencimiento', 'numero'
        ) if venta else CuotaVentaTienda.objects.none()
        self.fields['cuota'].queryset = cuotas_pendientes
        primera_cuota = cuotas_pendientes.first()
        if primera_cuota:
            self.fields['cuota'].initial = primera_cuota
            self.fields['cuota'].label_from_instance = lambda cuota: (
                f'Cuota {cuota.numero} - vence {cuota.fecha_vencimiento:%d/%m/%Y} - '
                f'saldo {number_format(cuota.saldo, decimal_pos=2, force_grouping=True)} '
                f'{cuota.venta.moneda}'
            )

    def clean_valor(self):
        valor = self.cleaned_data['valor']
        if self.venta and valor > self.venta.saldo_pendiente:
            raise forms.ValidationError('El abono no puede superar el saldo pendiente.')
        return valor

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('cuota') and self.venta:
            cleaned['cuota'] = self.venta.cuotas.filter(saldo__gt=0).order_by(
                'fecha_vencimiento', 'numero'
            ).first()
        return cleaned


class AjusteInventarioForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=ProductoTienda.objects.none(), widget=forms.Select(attrs={'class': 'form-select'})
    )
    tipo = forms.ChoiceField(
        choices=AjusteInventario.Tipos.choices, widget=forms.Select(attrs={'class': 'form-select'})
    )
    cantidad = forms.IntegerField(
        min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )
    motivo = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = ProductoTienda.objects.filter(activo=True)

    def clean(self):
        cleaned = super().clean()
        producto, tipo, cantidad = cleaned.get('producto'), cleaned.get('tipo'), cleaned.get('cantidad')
        if producto and tipo == AjusteInventario.Tipos.SALIDA and cantidad and cantidad > producto.stock:
            raise forms.ValidationError(
                f'No hay inventario suficiente. Existencias actuales: {producto.stock}.'
            )
        return cleaned
