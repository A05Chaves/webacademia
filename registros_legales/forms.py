from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UsernameField
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.utils import timezone
from .models import RegistroLegalEstudiante
from alumnos.models import Alumno
from django.contrib.auth import get_user_model
from config.file_validation import validate_base64_signature, validate_image
from instructores.models import Instructor
from planes.models import Plan

User = get_user_model()


def contactos_repetidos(correo='', celular='', excluir_registro_id=None):
    """Indica contactos compartidos sin tratarlos como identificadores únicos."""
    registros = RegistroLegalEstudiante.objects.exclude(
        estado=RegistroLegalEstudiante.Estados.RECHAZADO
    )
    if excluir_registro_id:
        registros = registros.exclude(pk=excluir_registro_id)

    coincidencias = {}
    correo = (correo or '').strip()
    celular = (celular or '').strip()

    if correo and (
        registros.filter(correo__iexact=correo).exists()
        or User.objects.filter(email__iexact=correo).exists()
    ):
        coincidencias['correo'] = (
            'Este correo ya está asociado a otro estudiante o acudiente.'
        )

    if celular and (
        registros.filter(Q(celular=celular) | Q(celular_acudiente=celular)).exists()
        or User.objects.filter(telefono=celular).exists()
        or Alumno.objects.filter(telefono_acudiente=celular).exists()
    ):
        coincidencias['celular'] = (
            'Este celular ya está asociado a otro estudiante o acudiente.'
        )

    return coincidencias


class RegistroLegalEstudianteForm(forms.ModelForm):
    usuario_solicitado = UsernameField(
        label='Usuario de acceso',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'username',
            'placeholder': 'Elige tu nombre de usuario',
        }),
        help_text='Este será el usuario con el que ingresarás al sistema.',
    )
    password1 = forms.CharField(
        label='Contraseña',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
        }),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
        }),
    )
    confirmar_contacto_repetido = forms.BooleanField(
        required=False,
        label=(
            'Confirmo que el correo y/o celular son correctos y pueden '
            'compartirse con otro estudiante.'
        ),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

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
            'confirmar_contacto_repetido',
            'usuario_solicitado',
            'password1',
            'password2',
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
                'class': 'form-control',
                'accept': '.jpg,.jpeg,.png,.webp'
            }),

            'nombres': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'apellidos': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'documento': forms.TextInput(attrs={
                'class': 'form-control',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'data-solo-numeros': 'true',
            }),

            'fecha_nacimiento': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),

            'direccion': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'celular': forms.TextInput(attrs={
                'class': 'form-control',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'data-solo-numeros': 'true',
            }),

            'correo': forms.EmailInput(attrs={
                'class': 'form-control'
            }),

            'fecha_ingreso': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'readonly': True,
            }),

            'plan_interes': forms.Select(attrs={
                'class': 'form-select'
            }),

            'contacto_emergencia_nombre': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'contacto_emergencia_celular': forms.TextInput(attrs={
                'class': 'form-control',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'data-solo-numeros': 'true',
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
                'class': 'form-control',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'data-solo-numeros': 'true',
            }),

            'parentesco_acudiente': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'celular_acudiente': forms.TextInput(attrs={
                'class': 'form-control',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'data-solo-numeros': 'true',
            }),

            'firma_base64': forms.HiddenInput(),

        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['plan_interes'].queryset = Plan.objects.filter(
            activo=True,
            precio__gt=0,
        ).exclude(nombre__icontains='beca')

        self.fields['fecha_ingreso'].label = 'Fecha de diligenciamiento del registro'
        self.fields['fecha_ingreso'].help_text = (
            'Se asigna automáticamente con la fecha en que diligencias este formulario; '
            'no corresponde al inicio del plan.'
        )
        self.fields['fecha_ingreso'].disabled = True
        self.fields['fecha_ingreso'].initial = (
            self.instance.fecha_ingreso
            if self.instance and self.instance.pk
            else timezone.localdate()
        )

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
            'usuario_solicitado',
            'password1',
            'password2',
            'fecha_ingreso',
            'plan_interes',
            'contacto_emergencia_nombre',
            'contacto_emergencia_celular',
            'eps',
            'condicion_medica',
            'acepta_reglamento',
            'acepta_riesgos',
            'autoriza_imagen',
            'firma_base64',
        ]

        for campo in campos_obligatorios:
            self.fields[campo].required = True

    def clean(self):
        cleaned_data = super().clean()

        cleaned_data['fecha_ingreso'] = (
            self.instance.fecha_ingreso
            if self.instance and self.instance.pk
            else timezone.localdate()
        )

        for campo in (
            'nombres', 'apellidos', 'contacto_emergencia_nombre',
            'nombre_acudiente',
        ):
            if cleaned_data.get(campo):
                cleaned_data[campo] = cleaned_data[campo].strip().title()

        tipo = cleaned_data.get('tipo_estudiante')

        campos_obligatorios = [
            'foto',
            'plan_interes',
            'nombres',
            'apellidos',
            'documento',
            'fecha_nacimiento',
            'direccion',
            'celular',
            'correo',
            'fecha_ingreso',
            'contacto_emergencia_nombre',
            'contacto_emergencia_celular',
            'eps',
            'condicion_medica',
        ]

        for campo in campos_obligatorios:
            if not cleaned_data.get(campo) and campo not in self.errors:
                self.add_error(
                    campo,
                    'Este campo es obligatorio.'
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

        if not cleaned_data.get('autoriza_imagen'):
            self.add_error(
                'autoriza_imagen',
                'Debe aceptar la autorización de imagen.'
            )

        firma = cleaned_data.get('firma_base64')

        if not firma or len(firma) < 100:
            self.add_error(
                'firma_base64',
                'Debe realizar la firma antes de enviar el formulario.'
            )

        if tipo == 'MENOR':
            campos_menor = [
                'nombre_acudiente',
                'documento_acudiente',
                'parentesco_acudiente',
                'celular_acudiente',
            ]

            for campo in campos_menor:
                if not cleaned_data.get(campo):
                    self.add_error(
                        campo,
                        'Este campo es obligatorio para menores de edad.'
                    )

        documento = cleaned_data.get('documento')
        celular = cleaned_data.get('celular')
        correo = cleaned_data.get('correo')

        if documento:
            existe_registro = RegistroLegalEstudiante.objects.filter(
                documento=documento
            ).exclude(
                estado=RegistroLegalEstudiante.Estados.RECHAZADO
            ).exists()

            existe_alumno = Alumno.objects.filter(
                documento=documento
            ).exists()

            existe_instructor = Instructor.objects.filter(
                documento=documento
            ).exists()

            if (
                existe_registro
                or existe_alumno
                or existe_instructor
            ):
                self.add_error(
                    'documento',
                    'Ya existe un estudiante o registro con este documento, o está asignado a un instructor.'
                )

        coincidencias_contacto = contactos_repetidos(
            correo,
            celular,
            self.instance.pk if self.instance and self.instance.pk else None,
        )
        if (
            coincidencias_contacto
            and not cleaned_data.get('confirmar_contacto_repetido')
        ):
            detalles = ' '.join(coincidencias_contacto.values())
            self.add_error(
                'confirmar_contacto_repetido',
                f'{detalles} Confirma que los datos son correctos para continuar.',
            )

        return cleaned_data

    def _validar_solo_numeros(self, campo, etiqueta):
        valor = (self.cleaned_data.get(campo) or '').strip()
        if valor and not valor.isdigit():
            raise forms.ValidationError(
                f'{etiqueta} solo puede contener números.'
            )
        return valor

    def clean_documento(self):
        return self._validar_solo_numeros('documento', 'El documento')

    def clean_celular(self):
        return self._validar_solo_numeros('celular', 'El celular')

    def clean_contacto_emergencia_celular(self):
        return self._validar_solo_numeros(
            'contacto_emergencia_celular', 'El celular de emergencia'
        )

    def clean_documento_acudiente(self):
        return self._validar_solo_numeros(
            'documento_acudiente', 'El documento del acudiente'
        )

    def clean_celular_acudiente(self):
        return self._validar_solo_numeros(
            'celular_acudiente', 'El celular del acudiente'
        )

    def clean_usuario_solicitado(self):
        username = self.cleaned_data['usuario_solicitado'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        registros = RegistroLegalEstudiante.objects.filter(
            usuario_solicitado__iexact=username,
        ).exclude(estado=RegistroLegalEstudiante.Estados.RECHAZADO)
        if self.instance.pk:
            registros = registros.exclude(pk=self.instance.pk)
        if registros.exists():
            raise forms.ValidationError(
                'Este nombre de usuario ya está reservado por otro registro.'
            )
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return password2

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get('password2')
        if password:
            usuario_temporal = User(
                username=self.cleaned_data.get('usuario_solicitado', '')
            )
            try:
                password_validation.validate_password(password, usuario_temporal)
            except forms.ValidationError as error:
                self.add_error('password2', error)

    def save(self, commit=True):
        registro = super().save(commit=False)
        password = self.cleaned_data.get('password1')
        if password:
            registro.password_hash = make_password(password)
        if commit:
            registro.save()
            self.save_m2m()
        return registro

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if foto:
            validate_image(foto)
        return foto

    def clean_firma_base64(self):
        firma = self.cleaned_data.get('firma_base64')
        if not firma:
            raise forms.ValidationError(
                'Debe realizar la firma antes de enviar el formulario.'
            )
        validate_base64_signature(firma)
        return firma
