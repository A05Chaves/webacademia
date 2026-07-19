from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import (
    AjusteInventario,
    CategoriaProducto,
    ClienteTienda,
    CuentaTienda,
    CuotaVentaTienda,
    ProductoTienda,
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


class CuentaTiendaForm(BootstrapModelForm):
    class Meta:
        model = CuentaTienda
        fields = [
            'nombre', 'tipo', 'moneda', 'saldo_inicial',
            'fecha_saldo_inicial', 'activa',
        ]
        widgets = {'fecha_saldo_inicial': forms.DateInput(attrs={'type': 'date'})}


class CategoriaProductoForm(BootstrapModelForm):
    class Meta:
        model = CategoriaProducto
        fields = ['codigo', 'nombre', 'activa']


class SubcategoriaProductoForm(BootstrapModelForm):
    class Meta:
        model = SubcategoriaProducto
        fields = ['categoria', 'codigo', 'nombre', 'activa']


class ClienteTiendaForm(BootstrapModelForm):
    class Meta:
        model = ClienteTienda
        fields = [
            'nombres', 'tipo_documento', 'numero_documento',
            'telefono_whatsapp', 'correo', 'direccion', 'acepta_whatsapp',
            'preferencial', 'descuento_preferencial', 'activo',
        ]


class ProductoTiendaForm(BootstrapModelForm):
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
            'url_imagen', 'ubicacion', 'proveedor', 'codigo_proveedor', 'moneda',
            'costo_unitario', 'precio_venta', 'stock_minimo', 'activo',
            'motivo_inactivacion',
        ]
        widgets = {'descripcion': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['moneda'].required = False
        self.fields['moneda'].initial = 'COP'
        self.fields['unidad'].required = False
        self.fields['unidad'].initial = 'Unidad'
        if self.instance and self.instance.pk:
            self.fields.pop('stock_inicial')

    def clean_moneda(self):
        return self.cleaned_data.get('moneda') or 'COP'

    def clean_unidad(self):
        return self.cleaned_data.get('unidad') or 'Unidad'


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
    modalidad = forms.ChoiceField(
        choices=VentaTienda.Modalidades.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    cliente = forms.ModelChoiceField(
        queryset=ClienteTienda.objects.filter(activo=True), required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Obligatorio para ventas a crédito y para emitir paz y salvo.',
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
    comprador_acepta_whatsapp = forms.BooleanField(
        required=False, label='Autoriza comprobantes y recordatorios por WhatsApp',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = ProductoTienda.objects.filter(
            activo=True, stock__gt=0, precio_venta__gt=0
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


class CompraTiendaForm(OperacionProductoForm):
    costo_unitario = forms.DecimalField(
        min_value=Decimal('0.01'), max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
        help_text='Costo real pagado por unidad en esta compra.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = ProductoTienda.objects.filter(activo=True)


class GastoTiendaForm(forms.Form):
    cuenta = forms.ModelChoiceField(
        queryset=CuentaTienda.objects.none(), widget=forms.Select(attrs={'class': 'form-select'})
    )
    concepto = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta'].queryset = CuentaTienda.objects.filter(activa=True)


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
                f'saldo {cuota.saldo:,.2f} {cuota.venta.moneda}'
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
