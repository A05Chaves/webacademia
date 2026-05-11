from django import forms
from .models import ClaseCortesia


class ClaseCortesiaForm(forms.ModelForm):

    consentimiento = forms.BooleanField(
        required=True,
        label='Acepto el consentimiento informado'
    )

    firma_base64 = forms.CharField(
        widget=forms.HiddenInput()
    )

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
