from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.db.models import Q


class RecuperarPasswordIdentificadoForm(PasswordResetForm):
    identificador = forms.CharField(
        label='Usuario o documento del estudiante',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'username',
            'placeholder': 'Usuario o número de documento',
        }),
        help_text=(
            'Este dato permite identificar la cuenta correcta cuando varias '
            'personas de la familia comparten el mismo correo.'
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Correo registrado'
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'autocomplete': 'email',
            'placeholder': 'correo@ejemplo.com',
        })
        self.order_fields(['identificador', 'email'])

    def get_users(self, email):
        identificador = self.cleaned_data.get('identificador', '').strip()
        usuarios = get_user_model()._default_manager.filter(
            email__iexact=email,
            is_active=True,
        ).filter(
            Q(username__iexact=identificador)
            | Q(perfil_alumno__documento__iexact=identificador)
        ).distinct()
        return (usuario for usuario in usuarios if usuario.has_usable_password())
