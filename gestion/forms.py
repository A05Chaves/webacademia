from pagos.models import Pago, MetodoPagoQR
from django import forms
from django.contrib.auth import get_user_model

from alumnos.models import Alumno
from planes.models import Plan, Suscripcion
from pagos.models import Pago
from pagos.models import MetodoPagoQR
from clases.models import ClaseProgramada

Usuario = get_user_model()


class UsuarioAlumnoForm(forms.ModelForm):
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Usuario
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'telefono',
            'password',
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
        }


class AlumnoForm(forms.ModelForm):
    class Meta:
        model = Alumno
        fields = [
            'documento',
            'fecha_nacimiento',
            'direccion',
            'disciplina',
            'grado',
            'nombre_acudiente',
            'telefono_acudiente',
            'estado',
        ]
        widgets = {
            'documento': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_nacimiento': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'disciplina': forms.Select(attrs={'class': 'form-select'}),
            'grado': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_acudiente': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_acudiente': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = [
            'nombre',
            'descripcion',
            'precio',
            'duracion_dias',
            'activo',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'precio': forms.NumberInput(attrs={'class': 'form-control'}),
            'duracion_dias': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SuscripcionForm(forms.ModelForm):
    class Meta:
        model = Suscripcion
        fields = [
            'alumno',
            'plan',
            'fecha_inicio',
            'fecha_vencimiento',
            'estado',
            'observaciones',
        ]

        widgets = {
            'alumno': forms.Select(attrs={'class': 'form-select'}),
            'plan': forms.Select(attrs={'class': 'form-select'}),

            'fecha_inicio': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),

            'fecha_vencimiento': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),

            'estado': forms.Select(attrs={'class': 'form-select'}),

            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = [
            'alumno',
            'suscripcion',
            'metodo_qr',
            'valor',
            'comprobante',
            'referencia_pago',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['metodo_qr'].queryset = MetodoPagoQR.objects.filter(
            activo=True)

    def clean(self):
        cleaned_data = super().clean()
        alumno = cleaned_data.get('alumno')
        suscripcion = cleaned_data.get('suscripcion')

        if alumno and suscripcion and suscripcion.alumno_id != alumno.id:
            raise forms.ValidationError(
                'La suscripción seleccionada no pertenece al alumno indicado.'
            )

        return cleaned_data


class ValidarPagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = [
            'estado',
            'observacion_admin',
        ]

    def clean_estado(self):
        estado = self.cleaned_data.get('estado')

        if estado not in ['APROBADO', 'RECHAZADO']:
            raise forms.ValidationError(
                'Solo puedes aprobar o rechazar el pago.'
            )

        return estado

# FORMULARIO PARA EDICION DE CLASES


class ClaseProgramadaForm(forms.ModelForm):
    class Meta:
        model = ClaseProgramada
        fields = [
            'dia',
            'hora_inicio',
            'hora_fin',
            'disciplina',
            'instructor',
            'cupo_maximo',
            'activa',
        ]
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
        }
