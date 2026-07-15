from django import forms
from django.utils import timezone

from .models import AjusteInventario, CuentaTienda, ProductoTienda


class CuentaTiendaForm(forms.ModelForm):
    class Meta:
        model = CuentaTienda
        fields = ['nombre', 'tipo', 'saldo_inicial', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'saldo_inicial': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductoTiendaForm(forms.ModelForm):
    stock_inicial = forms.IntegerField(
        min_value=0,
        initial=0,
        required=False,
        label='Inventario inicial',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        help_text='Después se modifica mediante compras o ajustes de inventario.',
    )

    class Meta:
        model = ProductoTienda
        fields = [
            'nombre', 'referencia', 'descripcion', 'precio_venta',
            'costo_unitario', 'stock_minimo', 'activo',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'referencia': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'precio_venta': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0.01', 'step': '0.01',
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'step': '0.01',
            }),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields.pop('stock_inicial')


class OperacionProductoForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=ProductoTienda.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    cantidad = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    cuenta = forms.ModelChoiceField(
        queryset=CuentaTienda.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta'].queryset = CuentaTienda.objects.filter(activa=True)


class VentaTiendaForm(OperacionProductoForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = ProductoTienda.objects.filter(
            activo=True,
            stock__gt=0,
        )


class CompraTiendaForm(OperacionProductoForm):
    costo_unitario = forms.DecimalField(
        min_value=0.01,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'min': '0.01', 'step': '0.01',
        }),
        help_text='Costo pagado por cada unidad en esta compra.',
    )
    actualizar_costo = forms.BooleanField(
        required=False,
        initial=True,
        label='Actualizar el costo unitario del producto',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = ProductoTienda.objects.filter(activo=True)


class GastoTiendaForm(forms.Form):
    cuenta = forms.ModelChoiceField(
        queryset=CuentaTienda.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    concepto = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    valor = forms.DecimalField(
        min_value=0.01,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'min': '0.01', 'step': '0.01',
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
        self.fields['cuenta'].queryset = CuentaTienda.objects.filter(activa=True)


class AjusteInventarioForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=ProductoTienda.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    tipo = forms.ChoiceField(
        choices=AjusteInventario.Tipos.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    cantidad = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    motivo = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Ejemplo: conteo físico, daño, pérdida o corrección.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = ProductoTienda.objects.filter(activo=True)

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        tipo = cleaned_data.get('tipo')
        cantidad = cleaned_data.get('cantidad')
        if (
            producto and tipo == AjusteInventario.Tipos.SALIDA
            and cantidad and cantidad > producto.stock
        ):
            raise forms.ValidationError(
                f'No hay inventario suficiente. Existencias actuales: {producto.stock}.'
            )
        return cleaned_data
