from django import forms
from .models import RegistroLegalEstudiante
from alumnos.models import Alumno
from django.contrib.auth import get_user_model

User = get_user_model()


class RegistroLegalEstudianteForm(forms.ModelForm):

    class Meta:
        model = RegistroLegalEstudiante

        fields = [
            'tipo_estudiante',

            'foto',

            'nombres',
            'apellidos',
            'documento',
            'fecha_nacimiento',
            'direccion',
            'celular',
            'correo',
            'fecha_ingreso',
            'plan_interes',
            'contacto_emergencia_nombre',
            'contacto_emergencia_celular',

            'eps',
            'condicion_medica',

            'nombre_acudiente',
            'documento_acudiente',
            'parentesco_acudiente',
            'celular_acudiente',

            'acepta_reglamento',
            'acepta_riesgos',
            'autoriza_imagen',
            'firma_base64',
        ]

        widgets = {

            'tipo_estudiante': forms.Select(attrs={
                'class': 'form-select'
            }),

            'foto': forms.FileInput(attrs={
                'class': 'form-control'
            }),

            'nombres': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'apellidos': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'documento': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'fecha_nacimiento': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),

            'direccion': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'celular': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'correo': forms.EmailInput(attrs={
                'class': 'form-control'
            }),

            'fecha_ingreso': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),

            'plan_interes': forms.Select(attrs={
                'class': 'form-select'
            }),

            'contacto_emergencia_nombre': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'contacto_emergencia_celular': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'eps': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Si no tiene escriba NINGUNA.'
            }),

            'condicion_medica': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Si no tiene alguna condición médica escriba NINGUNA.'
            }),

            'nombre_acudiente': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'documento_acudiente': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'parentesco_acudiente': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'celular_acudiente': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'firma_base64': forms.HiddenInput(),

        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        campos_obligatorios = [
            'tipo_estudiante',
            'foto',
            'nombres',
            'apellidos',
            'documento',
            'fecha_nacimiento',
            'direccion',
            'celular',
            'correo',
            'fecha_ingreso',
            'plan_interes',
            'contacto_emergencia_nombre',
            'contacto_emergencia_celular',
            'eps',
            'condicion_medica',
            'autoriza_imagen',
            'firma_base64',
        ]

        for campo in campos_obligatorios:
            self.fields[campo].required = True

    def clean(self):
        cleaned_data = super().clean()

        tipo = cleaned_data.get('tipo_estudiante')

        # Campos obligatorios para cualquier estudiante
        if not cleaned_data.get('foto'):
            self.add_error(
                'foto',
                'Debe adjuntar una foto del estudiante.'
            )

        if not cleaned_data.get('plan_interes'):
            self.add_error(
                'plan_interes',
                'Debe seleccionar el plan de interés.'
            )

        if not cleaned_data.get('acepta_reglamento'):
            self.add_error(
                'acepta_reglamento',
                'Debe aceptar el reglamento.'
            )

        if not cleaned_data.get('acepta_riesgos'):
            self.add_error(
                'acepta_riesgos',
                'Debe aceptar los riesgos deportivos.'
            )

        if not cleaned_data.get('firma_base64'):
            self.add_error(
                'firma_base64',
                'Debe adjuntar la firma del acudiente.'
            )

        # Campos obligatorios solo para menores de edad
        if tipo == 'MENOR':
            campos = [
                'nombre_acudiente',
                'documento_acudiente',
                'parentesco_acudiente',
                'celular_acudiente',
            ]

            for campo in campos:
                if not cleaned_data.get(campo):
                    self.add_error(
                        campo,
                        'Este campo es obligatorio para menores de edad.'
                    )

        documento = cleaned_data.get('documento')
        correo = cleaned_data.get('correo')
        celular = cleaned_data.get('celular')

        if documento:

            existe_registro = RegistroLegalEstudiante.objects.filter(
                documento=documento
            ).exists()

            existe_alumno = Alumno.objects.filter(
                documento=documento
            ).exists()

            existe_usuario = User.objects.filter(
                username=documento
            ).exists()

            if existe_registro or existe_alumno or existe_usuario:

                self.add_error(
                    'documento',
                    'Ya existe un estudiante o registro con este documento.'
                )

        if correo:

            existe_correo = RegistroLegalEstudiante.objects.filter(
                correo=correo
            ).exists()

            if existe_correo:

                self.add_error(
                    'correo',
                    'Ya existe un registro con este correo.'
                )

        if celular:

            existe_celular = RegistroLegalEstudiante.objects.filter(
                celular=celular
            ).exists()

            if existe_celular:

                self.add_error(
                    'celular',
                    'Ya existe un registro con este celular.'
                )

        return cleaned_data
