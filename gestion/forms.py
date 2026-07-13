from .models import ConfiguracionHome
from pagos.models import Pago, MetodoPagoQR
from django import forms
from django.contrib.auth import get_user_model
from .models import DiaHorario, HoraHorario
from alumnos.models import Alumno
from planes.models import Plan, Suscripcion
from pagos.models import Pago
from pagos.models import MetodoPagoQR
from clases.models import ClaseProgramada
from finanzas.models import MovimientoFinanciero, PagoProgramado, CuentaFinanciera, CategoriaFinanciera
from usuarios.models import Usuario
from django.contrib.auth.forms import PasswordChangeForm, UsernameField
from planes.models import Plan
from config.file_validation import validate_payment_receipt
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
            'permite_jiu_jitsu',
            'permite_muay_thai',
            'permite_mma',
            'clases_semana',
            'asistencia_ilimitada',
            'clases_mes',
            'activo',
        ]

        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),

            'precio': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),

            'duracion_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),

            'permite_jiu_jitsu': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),

            'permite_muay_thai': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),

            'permite_mma': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),

            'clases_semana': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),

            'asistencia_ilimitada': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),

            'clases_mes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),

            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
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
            'plan',
            'metodo_qr',
            'valor',
            'comprobante',
            'referencia_pago',
        ]

        widgets = {
            'alumno': forms.Select(attrs={'class': 'form-select'}),
            'plan': forms.Select(attrs={'class': 'form-select'}),
            'metodo_qr': forms.Select(attrs={'class': 'form-select'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'comprobante': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.webp',
            }),
            'referencia_pago': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['metodo_qr'].queryset = MetodoPagoQR.objects.filter(
            activo=True
        )

        self.fields['plan'].queryset = Plan.objects.filter(
            activo=True
        )

    def clean_comprobante(self):
        comprobante = self.cleaned_data.get('comprobante')
        if comprobante:
            validate_payment_receipt(comprobante)
        return comprobante


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
            'titulo',
            'publico_objetivo',
            'instructor',
            'cupo_maximo',
            'activa',
        ]

        widgets = {
            'dia': forms.Select(attrs={'class': 'form-select'}),
            'hora_inicio': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'hora_fin': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'disciplina': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Niños, Mujeres, Competencia'
            }),
            'publico_objetivo': forms.Select(attrs={'class': 'form-select'}),
            'instructor': forms.Select(attrs={'class': 'form-select'}),
            'cupo_maximo': forms.NumberInput(attrs={'class': 'form-control'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# FORMULARIO DE PAGO POR ESTUDIANTE


class PagoAlumnoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = [
            'plan',
            'metodo_qr',
            'valor',
            'comprobante',
            'referencia_pago',
        ]

        widgets = {
            'plan': forms.Select(attrs={'class': 'form-select'}),
            'metodo_qr': forms.Select(attrs={'class': 'form-select'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'comprobante': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.webp',
            }),
            'referencia_pago': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['plan'].queryset = Plan.objects.filter(
            activo=True
        )

        self.fields['metodo_qr'].queryset = MetodoPagoQR.objects.filter(
            activo=True
        )

    def clean_comprobante(self):
        comprobante = self.cleaned_data.get('comprobante')
        if comprobante:
            validate_payment_receipt(comprobante)
        return comprobante

# FORMULARIO DE GASTOS


class GastoForm(forms.ModelForm):
    class Meta:
        model = MovimientoFinanciero
        fields = [
            'cuenta',
            'categoria',
            'concepto',
            'valor',
            'fecha',
            'observaciones',
        ]

        widgets = {
            'cuenta': forms.Select(attrs={'class': 'form-select'}),
            'concepto': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),

        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.fields['categoria'].queryset = CategoriaFinanciera.objects.filter(
                activa=True
            ).filter(
                tipo__in=['EGRESO', 'AMBOS']
            )

# PAGOS PROGRAMADOS


class PagoProgramadoForm(forms.ModelForm):
    class Meta:
        model = PagoProgramado
        fields = [
            'concepto',
            'valor',
            'fecha_vencimiento',
            'cuenta_pago',
            'observaciones',
        ]

        widgets = {
            'concepto': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'fecha_vencimiento': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'cuenta_pago': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }

# TRANSFERENCAS ENTRE CUENTAS


class TransferenciaForm(forms.Form):
    cuenta_origen = forms.ModelChoiceField(
        queryset=CuentaFinanciera.objects.filter(activa=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Cuenta origen'
    )

    cuenta_destino = forms.ModelChoiceField(
        queryset=CuentaFinanciera.objects.filter(activa=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Cuenta destino'
    )

    valor = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Valor'
    )

    concepto = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Concepto'
    )

    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3
        }),
        label='Observaciones'
    )

    def clean(self):
        cleaned_data = super().clean()
        origen = cleaned_data.get('cuenta_origen')
        destino = cleaned_data.get('cuenta_destino')
        valor = cleaned_data.get('valor')

        if origen and destino and origen == destino:
            raise forms.ValidationError(
                'La cuenta origen y destino no pueden ser la misma.'
            )

        if origen and valor and valor > origen.saldo_actual:
            raise forms.ValidationError(
                'La cuenta origen no tiene saldo suficiente.'
            )

        return cleaned_data

# CAMBIO DE CONTRASEÑA OBLIGATORIO


class UsernameUnicoMixin:
    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        queryset = Usuario.objects.filter(username__iexact=username)

        if self.user.pk:
            queryset = queryset.exclude(pk=self.user.pk)

        if queryset.exists():
            raise forms.ValidationError(
                'Este nombre de usuario ya está en uso. Elige otro.'
            )

        return username


class CambioPasswordObligatorioForm(UsernameUnicoMixin, PasswordChangeForm):
    username = UsernameField(
        label='Nombre de usuario',
        max_length=150,
        validators=Usuario._meta.get_field('username').validators,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'username',
        }),
        help_text='Puedes conservarlo o cambiarlo. Solo podrás cambiarlo una vez.',
    )

    field_order = ('username', 'old_password', 'new_password1', 'new_password2')

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['username'].initial = user.username
        if user.username_modificado:
            self.fields['username'].disabled = True
            self.fields['username'].help_text = (
                'Ya utilizaste el cambio único de nombre de usuario.'
            )

    def save(self, commit=True):
        username_anterior = self.user.username
        username_nuevo = self.cleaned_data['username']
        self.user.username = username_nuevo

        if username_nuevo != username_anterior:
            self.user.username_modificado = True

        return super().save(commit=commit)


class CambiarUsuarioForm(UsernameUnicoMixin, forms.Form):
    username = UsernameField(
        label='Nuevo nombre de usuario',
        max_length=150,
        validators=Usuario._meta.get_field('username').validators,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'username',
        }),
        help_text='Este cambio solo se puede realizar una vez.',
    )
    password_actual = forms.CharField(
        label='Contraseña actual',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'current-password',
        }),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = super().clean_username()

        if self.user.username_modificado:
            raise forms.ValidationError(
                'Ya utilizaste el cambio de nombre de usuario disponible.'
            )

        if username == self.user.username:
            raise forms.ValidationError(
                'El nuevo nombre debe ser diferente al usuario actual.'
            )

        return username

    def clean_password_actual(self):
        password = self.cleaned_data['password_actual']
        if not self.user.check_password(password):
            raise forms.ValidationError('La contraseña actual es incorrecta.')
        return password

    def save(self):
        self.user.username = self.cleaned_data['username']
        self.user.username_modificado = True
        self.user.save(update_fields=['username', 'username_modificado'])
        return self.user

# FORMULARIO PARA EDICION DE ALUMNO


class UsuarioAlumnoEditForm(forms.ModelForm):

    class Meta:
        model = Usuario

        fields = [
            'first_name',
            'last_name',
            'email',
            'telefono',
        ]

        widgets = {

            'first_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'last_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'email': forms.EmailInput(attrs={
                'class': 'form-control'
            }),

            'telefono': forms.TextInput(attrs={
                'class': 'form-control'
            }),

        }


# FORMULARIO PARA AGREGAR VIDEO Y MUSICA


class ConfiguracionHomeForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionHome
        fields = [
            'video_promo_url',
            'video_promo_archivo',
            'playlist_youtube_url',
            'activo',
        ]

        widgets = {
            'video_promo_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://www.youtube.com/watch?v=...'
            }),
            'video_promo_archivo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'video/mp4'
            }),
            'playlist_youtube_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://www.youtube.com/playlist?list=...'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

        help_texts = {
            'video_promo_url': 'Pegue el enlace de un video normal de YouTube.',
            'playlist_youtube_url': 'Pegue una playlist real de YouTube. No use enlaces Radio/Mix.',
        }


# FORMULARIO PARA CONFIGURACION DE NOTIFICACIONES


class DiaHorarioForm(forms.ModelForm):
    class Meta:
        model = DiaHorario
        fields = ['nombre', 'orden', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class HoraHorarioForm(forms.ModelForm):
    class Meta:
        model = HoraHorario
        fields = ['hora', 'orden', 'activo']
        widgets = {
            'hora': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
