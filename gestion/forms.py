from pagos.models import Pago, MetodoPagoQR
from django import forms
from django.contrib.auth import get_user_model

from alumnos.models import Alumno
from planes.models import Plan, Suscripcion
from pagos.models import Pago
from pagos.models import MetodoPagoQR

Usuario = get_user_model()


class UsuarioAlumnoForm(forms.ModelForm):
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput
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

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


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
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
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


class SuscripcionForm(forms.ModelForm):
    class Meta:
        model = Suscripcion
        fields = [
            'alumno',
            'plan',
            'fecha_inicio',
            'fecha_vencimiento',
            'observaciones',
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        alumno = cleaned_data.get('alumno')

        if alumno:
            existe = Suscripcion.objects.filter(
                alumno=alumno,
                estado__in=['ACTIVA', 'PENDIENTE_PAGO']
            ).exists()

            if existe:
                raise forms.ValidationError(
                    'Este alumno ya tiene una suscripción activa o pendiente.'
                )

        return cleaned_data


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
