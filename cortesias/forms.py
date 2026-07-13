from django import forms
from config.file_validation import validate_base64_signature
from .models import ClaseCortesia


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

        if tipo_persona == ClaseCortesia.TiposPersona.MENOR:
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
            if tipo_persona == ClaseCortesia.TiposPersona.ADULTO and edad < 18:
                self.add_error(
                    'edad',
                    'Para una cortesía de adulto, la edad debe ser de 18 años o más.'
                )
            elif tipo_persona == ClaseCortesia.TiposPersona.MENOR and edad >= 18:
                self.add_error(
                    'edad',
                    'Para una cortesía de menor, la edad debe ser inferior a 18 años.'
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

        if tipo_persona == ClaseCortesia.TiposPersona.MENOR:
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
