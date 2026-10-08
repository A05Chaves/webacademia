from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import UsernameField
from django.contrib.auth.hashers import make_password

from alumnos.models import Alumno
from config.file_validation import validate_image
from registros_legales.models import RegistroLegalEstudiante

from .models import Instructor, SolicitudRegistroProfesor


User = get_user_model()


class SolicitudRegistroProfesorForm(forms.ModelForm):
    usuario_solicitado = UsernameField(
        label='Usuario de acceso',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'autocomplete': 'username',
        }),
    )
    password1 = forms.CharField(
        label='Contraseña',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'autocomplete': 'new-password',
        }),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'autocomplete': 'new-password',
        }),
    )

    class Meta:
        model = SolicitudRegistroProfesor
        fields = [
            'foto', 'nombres', 'apellidos', 'documento', 'celular', 'correo',
            'especialidad', 'usuario_solicitado', 'password1', 'password2',
        ]
        widgets = {
            'foto': forms.FileInput(attrs={
                'class': 'form-control', 'accept': '.jpg,.jpeg,.png,.webp',
            }),
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'documento': forms.TextInput(attrs={
                'class': 'form-control', 'inputmode': 'numeric',
                'data-solo-numeros': 'true',
            }),
            'celular': forms.TextInput(attrs={
                'class': 'form-control', 'inputmode': 'numeric',
                'data-solo-numeros': 'true',
            }),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'especialidad': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_documento(self):
        documento = (self.cleaned_data.get('documento') or '').replace('.', '').strip()
        if not documento.isdigit():
            raise forms.ValidationError('El documento solo puede contener números.')
        existente = SolicitudRegistroProfesor.objects.filter(
            documento__iexact=documento,
        ).exclude(estado=SolicitudRegistroProfesor.Estados.RECHAZADO).first()
        if existente:
            if existente.estado == SolicitudRegistroProfesor.Estados.PENDIENTE:
                raise forms.ValidationError(
                    'Este registro de profesor ya está pendiente de aprobación.'
                )
            raise forms.ValidationError('Este registro de profesor ya fue aprobado.')
        if (
            Instructor.objects.filter(documento=documento).exists()
            or Alumno.objects.filter(documento=documento).exists()
            or RegistroLegalEstudiante.objects.filter(
                documento__iexact=documento,
            ).exclude(
                estado=RegistroLegalEstudiante.Estados.RECHAZADO
            ).exists()
        ):
            raise forms.ValidationError(
                'Este documento ya pertenece a un usuario de la academia. '
                'El administrador puede agregarle el perfil de profesor.'
            )
        return documento

    def clean_celular(self):
        celular = (self.cleaned_data.get('celular') or '').strip()
        if celular and not celular.isdigit():
            raise forms.ValidationError('El celular solo puede contener números.')
        return celular

    def clean_usuario_solicitado(self):
        username = self.cleaned_data['usuario_solicitado'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        if SolicitudRegistroProfesor.objects.filter(
            usuario_solicitado__iexact=username,
        ).exclude(estado=SolicitudRegistroProfesor.Estados.RECHAZADO).exists():
            raise forms.ValidationError(
                'Este nombre de usuario ya está reservado por otra solicitud.'
            )
        if RegistroLegalEstudiante.objects.filter(
            usuario_solicitado__iexact=username,
        ).exclude(
            estado=RegistroLegalEstudiante.Estados.RECHAZADO
        ).exists():
            raise forms.ValidationError(
                'Este nombre de usuario está reservado por un registro de estudiante.'
            )
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return password2

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if foto:
            validate_image(foto)
        return foto

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get('password2')
        if password:
            temporal = User(username=self.cleaned_data.get('usuario_solicitado', ''))
            try:
                password_validation.validate_password(password, temporal)
            except forms.ValidationError as error:
                self.add_error('password2', error)

    def save(self, commit=True):
        solicitud = super().save(commit=False)
        solicitud.password_hash = make_password(self.cleaned_data['password1'])
        if commit:
            solicitud.save()
        return solicitud
