from django import forms
from config.file_validation import validate_base64_signature
from .models import ClaseCortesia, ConfiguracionSeguimientoCortesia


class ClaseCortesiaForm(forms.ModelForm):

    consentimiento = forms.BooleanField(
        required=True,
        label='Acepto el consentimiento informado'
    )

    firma_base64 = forms.CharField(
        widget=forms.HiddenInput(),
        validators=[validate_base64_signature],
    )

    def __init__(self, *args, tipo_persona=None, publico_objetivo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tipo_persona_bloqueado = tipo_persona
        self.publico_objetivo = publico_objetivo

        if tipo_persona in {
            ClaseCortesia.TiposPersona.ADULTO,
            ClaseCortesia.TiposPersona.MENOR,
        }:
            self.fields['tipo_persona'].initial = tipo_persona
            self.fields['tipo_persona'].disabled = True

        edad_informada = None
        if self.is_bound:
            try:
                edad_informada = int(self.data.get(self.add_prefix('edad'), ''))
            except (TypeError, ValueError):
                pass

        if tipo_persona == ClaseCortesia.TiposPersona.MENOR or (
            edad_informada is not None and edad_informada < 18
        ):
            for field_name in (
                'nombre_acudiente',
                'documento_acudiente',
                'telefono_acudiente',
                'parentesco_acudiente',
            ):
                self.fields[field_name].required = True

    def clean(self):
        cleaned_data = super().clean()
        tipo_persona = cleaned_data.get('tipo_persona')
        edad = cleaned_data.get('edad')

        if edad is not None:
            tipo_por_edad = (
                ClaseCortesia.TiposPersona.ADULTO
                if edad >= 15
                else ClaseCortesia.TiposPersona.MENOR
            )
            if self.publico_objetivo is None:
                tipo_persona = tipo_por_edad
                cleaned_data['tipo_persona'] = tipo_por_edad
            elif tipo_persona == ClaseCortesia.TiposPersona.ADULTO and edad < 15:
                self.add_error(
                    'edad',
                    'Las clases de adultos están disponibles desde los 15 años.'
                )
            elif tipo_persona == ClaseCortesia.TiposPersona.MENOR and edad >= 15:
                self.add_error(
                    'edad',
                    'Las clases para niños están disponibles hasta los 14 años.'
                )

        if (
            self.publico_objetivo
            and self.publico_objetivo != 'TODOS'
            and tipo_persona != self.publico_objetivo
        ):
            self.add_error(
                'tipo_persona',
                'La clase seleccionada no corresponde a este tipo de participante.'
            )

        if edad is not None and edad < 18:
            guardian_fields = {
                'nombre_acudiente': 'Ingresa el nombre del acudiente.',
                'documento_acudiente': 'Ingresa el documento del acudiente.',
                'telefono_acudiente': 'Ingresa el teléfono del acudiente.',
                'parentesco_acudiente': 'Indica el parentesco del acudiente.',
            }
            for field_name, error_message in guardian_fields.items():
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, error_message)

        return cleaned_data

    class Meta:
        model = ClaseCortesia

        fields = [
            'nombres',
            'apellidos',
            'documento',
            'telefono',
            'correo',
            'edad',
            'tipo_persona',
            'eps',
            'condicion_medica',
            'nombre_acudiente',
            'documento_acudiente',
            'telefono_acudiente',
            'parentesco_acudiente',
        ]

        widgets = {

            'nombres': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'apellidos': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'documento': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'telefono': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'correo': forms.EmailInput(attrs={
                'class': 'form-control'
            }),

            'edad': forms.NumberInput(attrs={
                'class': 'form-control'
            }),

            'tipo_persona': forms.Select(attrs={
                'class': 'form-select'
            }),
            'eps': forms.TextInput(attrs={'class': 'form-control'}),

            'condicion_medica': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Indique si tiene discapacidad, lesión, enfermedad o condición relevante.'
            }),

            'nombre_acudiente': forms.TextInput(attrs={'class': 'form-control'}),
            'documento_acudiente': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_acudiente': forms.TextInput(attrs={'class': 'form-control'}),
            'parentesco_acudiente': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ConfiguracionSeguimientoCortesiaForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionSeguimientoCortesia
        fields = [
            'activo', 'dias_espera', 'intervalo_dias', 'maximo_envios',
            'asunto', 'mensaje', 'publicidad',
        ]
        widgets = {
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dias_espera': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 365}),
            'intervalo_dias': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
            'maximo_envios': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'asunto': forms.TextInput(attrs={'class': 'form-control'}),
            'mensaje': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'publicidad': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
