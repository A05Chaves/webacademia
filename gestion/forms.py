from .models import ConfiguracionHome
from datetime import timedelta

from django.utils import timezone

from pagos.models import (
    AcademiaCompetidora, CategoriaEvento, Evento, InscripcionEvento,
    MetodoPagoQR, Pago, Promocion,
)
from django import forms
from django.db.models import Q
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
from config.file_validation import (
    validate_base64_signature, validate_image, validate_payment_receipt,
)
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
            'documento_acudiente',
            'parentesco_acudiente',
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
            'documento_acudiente': forms.TextInput(attrs={'class': 'form-control'}),
            'parentesco_acudiente': forms.TextInput(attrs={'class': 'form-control'}),
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
    fecha_inicio = forms.DateField(
        required=False,
        label='Fecha real de inicio',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    confirmar_duplicado = forms.BooleanField(
        required=False,
        label='Confirmo que revisé la coincidencia y el pago es legítimo',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    justificacion_duplicado = forms.CharField(
        required=False,
        label='Justificación',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )

    class Meta:
        model = Pago
        fields = [
            'estado',
            'observacion_admin',
        ]

        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'observacion_admin': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
            }),
        }

    def __init__(self, *args, **kwargs):
        self.pago = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if self.pago and self.pago.tipo in (
            Pago.Tipos.MENSUALIDAD, Pago.Tipos.PROMOCION,
        ):
            hoy = timezone.localdate()
            ultima = Suscripcion.objects.filter(
                alumno=self.pago.alumno
            ).order_by('-fecha_vencimiento').first()
            inicio = (
                ultima.fecha_vencimiento + timedelta(days=1)
                if ultima and ultima.fecha_vencimiento >= hoy else hoy
            )
            self.fields['fecha_inicio'].initial = inicio
        else:
            self.fields['fecha_inicio'].widget = forms.HiddenInput()

    def clean_estado(self):
        estado = self.cleaned_data.get('estado')

        if estado not in ['APROBADO', 'RECHAZADO']:
            raise forms.ValidationError(
                'Solo puedes aprobar o rechazar el pago.'
            )

        return estado

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('estado') == Pago.Estados.APROBADO:
            if self.pago.tipo in (Pago.Tipos.MENSUALIDAD, Pago.Tipos.PROMOCION):
                if not cleaned.get('fecha_inicio'):
                    cleaned['fecha_inicio'] = self.fields['fecha_inicio'].initial
            if self.pago.posible_duplicado:
                if not cleaned.get('confirmar_duplicado'):
                    self.add_error(
                        'confirmar_duplicado',
                        'Debes confirmar que revisaste el posible duplicado.',
                    )
                if not cleaned.get('justificacion_duplicado', '').strip():
                    self.add_error(
                        'justificacion_duplicado',
                        'Explica por qué este pago no es un duplicado.',
                    )
        return cleaned

    def fecha_vencimiento_calculada(self):
        inicio = self.cleaned_data['fecha_inicio']
        dias = (
            self.pago.promocion.dias_aplicados
            if self.pago.promocion_id else self.pago.plan.duracion_dias
        )
        return inicio + timedelta(days=dias - 1)


class PromocionForm(forms.ModelForm):
    class Meta:
        model = Promocion
        fields = [
            'nombre', 'descripcion', 'plan', 'tipo_beneficio',
            'valor_beneficio', 'condiciones', 'publico', 'fecha_inicio',
            'fecha_fin', 'maximo_usos', 'un_uso_por_alumno', 'imagen',
            'video',
            'publicada_home', 'destacada', 'orden', 'activa',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'condiciones': forms.Textarea(attrs={'rows': 3}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}),
            'video': forms.ClearableFileInput(attrs={'accept': 'video/mp4,video/webm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs['class'] = 'form-check-input'
            else:
                campo.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('fecha_inicio') and cleaned.get('fecha_fin'):
            if cleaned['fecha_fin'] < cleaned['fecha_inicio']:
                self.add_error('fecha_fin', 'Debe ser posterior a la fecha inicial.')
        tipo = cleaned.get('tipo_beneficio')
        valor = cleaned.get('valor_beneficio')
        if valor is not None and valor < 0:
            self.add_error('valor_beneficio', 'El beneficio no puede ser negativo.')
        if tipo == Promocion.TiposBeneficio.PORCENTAJE and valor and valor > 100:
            self.add_error('valor_beneficio', 'El porcentaje no puede superar 100.')
        return cleaned


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            'tipo', 'nombre', 'descripcion', 'fecha_inicio', 'fecha_fin',
            'fecha_inicio_inscripcion', 'fecha_limite_inscripcion',
            'lugar', 'precio_estudiante',
            'precio_externo', 'cupo_maximo', 'publico', 'requisitos',
            'alcance_torneo', 'consentimiento_evento', 'imagen',
            'video',
            'reglamento_adultos', 'reglamento_menores',
            'publicada_home', 'destacada', 'orden', 'activo',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'requisitos': forms.Textarea(attrs={'rows': 3}),
            'consentimiento_evento': forms.Textarea(attrs={'rows': 7}),
            'reglamento_adultos': forms.Textarea(attrs={'rows': 7}),
            'reglamento_menores': forms.Textarea(attrs={'rows': 7}),
            'fecha_inicio': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}
            ),
            'fecha_fin': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}
            ),
            'fecha_inicio_inscripcion': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}
            ),
            'fecha_limite_inscripcion': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}
            ),
            'video': forms.ClearableFileInput(attrs={'accept': 'video/mp4,video/webm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in (
            'fecha_inicio', 'fecha_fin', 'fecha_inicio_inscripcion',
            'fecha_limite_inscripcion',
        ):
            self.fields[nombre].input_formats = ['%Y-%m-%dT%H:%M']
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs['class'] = 'form-check-input'
            else:
                campo.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get('fecha_inicio')
        fin = cleaned.get('fecha_fin')
        inicio_inscripciones = cleaned.get('fecha_inicio_inscripcion')
        limite = cleaned.get('fecha_limite_inscripcion')
        if inicio and fin and fin < inicio:
            self.add_error('fecha_fin', 'La fecha final no puede ser anterior al inicio.')
        if inicio_inscripciones and limite and limite < inicio_inscripciones:
            self.add_error(
                'fecha_limite_inscripcion',
                'El cierre de inscripciones debe ser posterior a su apertura.',
            )
        if (
            cleaned.get('tipo') == Evento.Tipos.TORNEO
            and not (cleaned.get('consentimiento_evento') or '').strip()
        ):
            self.add_error(
                'consentimiento_evento',
                'Debes configurar el consentimiento que firmarán los participantes.',
            )
        if cleaned.get('tipo') == Evento.Tipos.TORNEO:
            publico = cleaned.get('publico')
            if publico != Evento.Publicos.MENORES and not (
                cleaned.get('reglamento_adultos') or ''
            ).strip():
                self.add_error(
                    'reglamento_adultos',
                    'Configura el reglamento para participantes adultos.',
                )
            if publico != Evento.Publicos.ADULTOS and not (
                cleaned.get('reglamento_menores') or ''
            ).strip():
                self.add_error(
                    'reglamento_menores',
                    'Configura el reglamento para menores y acudientes.',
                )
        if (
            cleaned.get('tipo') == Evento.Tipos.TORNEO
            and cleaned.get('publicada_home')
            and (
                not self.instance.pk
                or not self.instance.categorias.filter(activa=True).exists()
            )
        ):
            self.add_error(
                'publicada_home',
                'Guarda primero el torneo, crea sus categorías y después publícalo.',
            )
        return cleaned


class CategoriaEventoForm(forms.ModelForm):
    class Meta:
        model = CategoriaEvento
        fields = [
            'nombre', 'tipo_categoria', 'genero', 'edad_minima', 'edad_maxima',
            'peso_minimo', 'peso_maximo', 'nivel', 'cupo_maximo',
            'orden', 'activa',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs['class'] = 'form-check-input'
            else:
                campo.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        for minimo, maximo in (
            ('edad_minima', 'edad_maxima'), ('peso_minimo', 'peso_maximo')
        ):
            if (
                cleaned.get(minimo) is not None
                and cleaned.get(maximo) is not None
                and cleaned[maximo] < cleaned[minimo]
            ):
                self.add_error(maximo, 'No puede ser menor que el límite mínimo.')
        return cleaned


class InscripcionEventoForm(forms.ModelForm):
    academia_registrada = forms.ModelChoiceField(
        queryset=AcademiaCompetidora.objects.none(),
        required=False,
        label='Academia registrada',
        empty_label='Mi academia no aparece en la lista',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Selecciona una academia para reutilizar su nombre y escudo.',
    )
    logo_academia = forms.ImageField(
        required=False,
        label='Escudo o logo de la academia',
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control', 'accept': '.jpg,.jpeg,.png,.webp',
        }),
    )
    firma_base64 = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        validators=[validate_base64_signature],
    )
    metodo_qr = forms.ModelChoiceField(
        queryset=MetodoPagoQR.objects.none(),
        label='Método de pago',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    referencia_pago = forms.CharField(
        required=False, widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    comprobante = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png,.webp',
        }),
    )

    class Meta:
        model = InscripcionEvento
        fields = [
            'participante_nombre', 'participante_documento', 'fecha_nacimiento',
            'correo', 'telefono', 'academia_origen', 'foto_participante',
            'acudiente_nombre', 'acudiente_documento',
            'acudiente_telefono', 'categoria_evento', 'peso',
            'acepta_reglamento', 'acepta_consentimiento', 'firma_base64',
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'acepta_consentimiento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'acepta_reglamento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'foto_participante': forms.ClearableFileInput(attrs={
                'accept': '.jpg,.jpeg,.png,.webp',
            }),
        }

    def __init__(self, *args, evento=None, alumno_interno=None, **kwargs):
        self.evento = evento
        self.alumno_interno = alumno_interno
        super().__init__(*args, **kwargs)
        self.fields['metodo_qr'].queryset = MetodoPagoQR.objects.filter(activo=True)
        self.fields['academia_registrada'].queryset = (
            AcademiaCompetidora.objects.filter(
                activa=True, logo__isnull=False
            ).exclude(logo='').order_by('nombre')
        )
        self.fields['categoria_evento'].queryset = CategoriaEvento.objects.none()
        if evento and evento.tipo == Evento.Tipos.TORNEO:
            self.fields['categoria_evento'].queryset = evento.categorias.filter(
                activa=True
            )
            self.fields['categoria_evento'].required = True
            self.fields['peso'].required = True
            self.fields['firma_base64'].required = True
            if evento.alcance_torneo == Evento.AlcancesTorneo.ABIERTO:
                self.fields['academia_origen'].required = False
                self.fields['academia_origen'].label = 'Nombre de la nueva academia'
                self.fields['foto_participante'].required = True
            else:
                self.fields.pop('academia_registrada')
                self.fields.pop('logo_academia')
                self.fields.pop('academia_origen')
                self.fields.pop('foto_participante')
                for nombre in (
                    'participante_nombre', 'fecha_nacimiento', 'correo', 'telefono',
                    'acudiente_nombre', 'acudiente_documento', 'acudiente_telefono',
                ):
                    self.fields[nombre].required = False
        else:
            self.fields.pop('academia_registrada')
            self.fields.pop('logo_academia')
            self.fields.pop('categoria_evento')
            self.fields.pop('academia_origen')
            self.fields.pop('foto_participante')
            self.fields.pop('firma_base64')
        if evento and evento.precio_estudiante == 0 and evento.precio_externo == 0:
            self.fields.pop('metodo_qr')
            self.fields.pop('referencia_pago')
            self.fields.pop('comprobante')
        elif evento:
            precio_aplicable = (
                evento.precio_externo
                if (
                    evento.tipo == Evento.Tipos.TORNEO
                    and evento.alcance_torneo == Evento.AlcancesTorneo.ABIERTO
                )
                else evento.precio_estudiante
            )
            if precio_aplicable > 0:
                self.fields['referencia_pago'].required = True
                self.fields['comprobante'].required = True
        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs.setdefault('class', 'form-control')

    def clean_comprobante(self):
        archivo = self.cleaned_data.get('comprobante')
        precio_aplicable = 0
        if self.evento:
            precio_aplicable = (
                self.evento.precio_externo
                if (
                    self.evento.tipo == Evento.Tipos.TORNEO
                    and self.evento.alcance_torneo == Evento.AlcancesTorneo.ABIERTO
                )
                else self.evento.precio_estudiante
            )
        if precio_aplicable > 0 and not archivo:
            raise forms.ValidationError('Adjunta el comprobante de pago.')
        if archivo:
            validate_payment_receipt(archivo)
        return archivo

    def clean_foto_participante(self):
        foto = self.cleaned_data.get('foto_participante')
        if foto:
            validate_image(foto)
        return foto

    def clean_logo_academia(self):
        logo = self.cleaned_data.get('logo_academia')
        if logo:
            validate_image(logo)
        return logo

    def clean(self):
        cleaned = super().clean()
        if (
            self.evento
            and self.evento.tipo == Evento.Tipos.TORNEO
            and self.evento.alcance_torneo == Evento.AlcancesTorneo.INTERNO
        ):
            alumno = self.alumno_interno
            if not alumno:
                self.add_error(
                    'participante_documento',
                    'No encontramos un estudiante de la academia con este documento.',
                )
            else:
                faltantes = []
                if not alumno.fecha_nacimiento:
                    faltantes.append('fecha de nacimiento')
                if not alumno.user.email:
                    faltantes.append('correo')
                if not alumno.user.telefono:
                    faltantes.append('teléfono')
                if faltantes:
                    self.add_error(
                        'participante_documento',
                        'La ficha del estudiante debe completar: ' + ', '.join(faltantes) + '.',
                    )
                cleaned['participante_nombre'] = str(alumno)
                cleaned['fecha_nacimiento'] = alumno.fecha_nacimiento
                cleaned['correo'] = alumno.user.email or ''
                cleaned['telefono'] = alumno.user.telefono or ''
                cleaned['acudiente_nombre'] = alumno.nombre_acudiente or ''
                cleaned['acudiente_documento'] = alumno.documento_acudiente or ''
                cleaned['acudiente_telefono'] = alumno.telefono_acudiente or ''
        nacimiento = cleaned.get('fecha_nacimiento')
        edad = None
        if nacimiento:
            hoy = timezone.localdate()
            edad = hoy.year - nacimiento.year - (
                (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)
            )
            if self.evento and self.evento.publico == Evento.Publicos.ADULTOS and edad < 18:
                self.add_error('fecha_nacimiento', 'Este evento es únicamente para adultos.')
            if self.evento and self.evento.publico == Evento.Publicos.MENORES and edad >= 18:
                self.add_error('fecha_nacimiento', 'Este evento es únicamente para menores.')
            if edad < 18:
                for campo in ('acudiente_nombre', 'acudiente_documento', 'acudiente_telefono'):
                    if not cleaned.get(campo):
                        self.add_error(campo, 'Obligatorio para menores de edad.')
        categoria = cleaned.get('categoria_evento')
        if (
            self.evento
            and self.evento.tipo == Evento.Tipos.TORNEO
            and self.evento.alcance_torneo == Evento.AlcancesTorneo.ABIERTO
        ):
            academia_registrada = cleaned.get('academia_registrada')
            academia = (cleaned.get('academia_origen') or '').strip()
            if academia_registrada:
                academia = academia_registrada.nombre
                cleaned['academia_origen'] = academia
            if not academia:
                self.add_error(
                    'academia_origen',
                    'Selecciona una academia o escribe el nombre de una nueva.',
                )
            academia_existente = (
                academia_registrada
                or AcademiaCompetidora.objects.filter(
                    nombre__iexact=academia, activa=True
                ).first()
            )
            tiene_logo = bool(
                academia_existente
                and academia_existente.logo
                and academia_existente.logo.name
            )
            if academia and not cleaned.get('logo_academia') and not tiene_logo:
                self.add_error(
                    'logo_academia',
                    'Adjunta el logo para registrar esta academia por primera vez.',
                )
        peso = cleaned.get('peso')
        if categoria:
            if categoria.cupos_disponibles == 0:
                self.add_error('categoria_evento', 'Esta categoría ya no tiene cupos.')
            if edad is not None:
                if categoria.edad_minima is not None and edad < categoria.edad_minima:
                    self.add_error('categoria_evento', 'No cumples la edad mínima de esta categoría.')
                if categoria.edad_maxima is not None and edad > categoria.edad_maxima:
                    self.add_error('categoria_evento', 'Superas la edad máxima de esta categoría.')
            requiere_peso = (
                categoria.peso_minimo is not None
                or categoria.peso_maximo is not None
            )
            if requiere_peso and peso is None:
                self.add_error('peso', 'Indica el peso para validar la categoría.')
            elif peso is not None:
                if categoria.peso_minimo is not None and peso < categoria.peso_minimo:
                    self.add_error('peso', 'El peso es inferior al permitido en esta categoría.')
                if categoria.peso_maximo is not None and peso > categoria.peso_maximo:
                    self.add_error('peso', 'El peso supera el permitido en esta categoría.')
        if not cleaned.get('acepta_consentimiento'):
            self.add_error('acepta_consentimiento', 'Debes aceptar el consentimiento.')
        if (
            self.evento
            and self.evento.tipo == Evento.Tipos.TORNEO
            and not cleaned.get('acepta_reglamento')
        ):
            self.add_error('acepta_reglamento', 'Debes aceptar el reglamento del torneo.')
        return cleaned


class EditarInscripcionEventoForm(forms.ModelForm):
    """Edición administrativa sin reemplazar la evidencia legal firmada."""

    logo_academia = forms.ImageField(
        required=False,
        label='Nuevo escudo o logo de la academia',
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control', 'accept': '.jpg,.jpeg,.png,.webp',
        }),
        help_text='Opcional. Si lo adjuntas, reemplazará el logo actual de la academia.',
    )

    class Meta:
        model = InscripcionEvento
        fields = [
            'participante_nombre', 'participante_documento', 'fecha_nacimiento',
            'correo', 'telefono', 'academia_origen', 'foto_participante',
            'acudiente_nombre', 'acudiente_documento', 'acudiente_telefono',
            'categoria_evento', 'peso', 'estado',
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'foto_participante': forms.ClearableFileInput(attrs={
                'accept': '.jpg,.jpeg,.png,.webp',
            }),
        }
        help_texts = {
            'categoria_evento': (
                'Administración puede corregir la categoría aunque el peso o la '
                'edad queden fuera del rango configurado.'
            ),
        }

    def __init__(self, *args, evento=None, **kwargs):
        self.evento = evento or getattr(kwargs.get('instance'), 'evento', None)
        super().__init__(*args, **kwargs)
        for nombre in (
            'participante_nombre', 'participante_documento', 'fecha_nacimiento',
            'correo', 'telefono', 'categoria_evento', 'peso', 'estado',
        ):
            self.fields[nombre].required = True
        categorias = CategoriaEvento.objects.none()
        if self.evento:
            categorias = self.evento.categorias.filter(
                Q(activa=True) | Q(pk=self.instance.categoria_evento_id)
            )
        self.fields['categoria_evento'].queryset = categorias
        if (
            self.evento
            and self.evento.alcance_torneo == Evento.AlcancesTorneo.ABIERTO
        ):
            self.fields['academia_origen'].required = True
        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs.setdefault(
                    'class',
                    'form-select' if isinstance(campo.widget, forms.Select) else 'form-control',
                )

    def clean_foto_participante(self):
        foto = self.cleaned_data.get('foto_participante')
        if foto:
            validate_image(foto)
        return foto

    def clean_logo_academia(self):
        logo = self.cleaned_data.get('logo_academia')
        if logo:
            validate_image(logo)
        return logo

    def clean(self):
        cleaned = super().clean()
        nacimiento = cleaned.get('fecha_nacimiento')
        if nacimiento:
            hoy = timezone.localdate()
            edad = hoy.year - nacimiento.year - (
                (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)
            )
            if edad < 18:
                for campo in (
                    'acudiente_nombre', 'acudiente_documento', 'acudiente_telefono'
                ):
                    if not cleaned.get(campo):
                        self.add_error(campo, 'Obligatorio para menores de 18 años.')

        categoria = cleaned.get('categoria_evento')
        documento = (cleaned.get('participante_documento') or '').strip()
        if categoria and self.evento and categoria.evento_id != self.evento.id:
            self.add_error('categoria_evento', 'La categoría no pertenece a este evento.')
        if categoria and documento and self.evento:
            otras = InscripcionEvento.objects.filter(
                evento=self.evento,
                participante_documento__iexact=documento,
            ).exclude(pk=self.instance.pk).exclude(
                estado=InscripcionEvento.Estados.CANCELADA
            )
            if otras.filter(categoria_evento=categoria).exists():
                self.add_error(
                    'categoria_evento',
                    'El participante ya tiene una inscripción en esta categoría.',
                )
            elif otras.count() >= 2:
                self.add_error(
                    'participante_documento',
                    'El participante ya tiene el máximo de dos inscripciones en el evento.',
                )
            elif (
                categoria.tipo_categoria == CategoriaEvento.TiposCategoria.REGULAR
                and otras.filter(
                    categoria_evento__tipo_categoria=(
                        CategoriaEvento.TiposCategoria.REGULAR
                    )
                ).exists()
            ):
                self.add_error(
                    'categoria_evento',
                    'No puede conservar dos inscripciones en categorías regulares.',
                )
        return cleaned


class AplicarPromocionForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    metodo_qr = forms.ModelChoiceField(
        queryset=MetodoPagoQR.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    referencia_pago = forms.CharField(
        required=False, widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    comprobante = forms.FileField(widget=forms.ClearableFileInput(attrs={
        'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png,.webp',
    }))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['metodo_qr'].queryset = MetodoPagoQR.objects.filter(activo=True)

    def clean_comprobante(self):
        archivo = self.cleaned_data['comprobante']
        validate_payment_receipt(archivo)
        return archivo

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


class CuentaFinancieraForm(forms.ModelForm):
    class Meta:
        model = CuentaFinanciera
        fields = ['nombre', 'tipo', 'saldo_inicial', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'saldo_inicial': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


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
            'valor': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01',
            }),
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

        self.fields['cuenta'].queryset = CuentaFinanciera.objects.filter(
            activa=True
        )
        self.fields['categoria'].queryset = CategoriaFinanciera.objects.filter(
            activa=True,
            tipo__in=[
                CategoriaFinanciera.Tipos.EGRESO,
                CategoriaFinanciera.Tipos.AMBOS,
            ],
        )

    def clean_valor(self):
        valor = self.cleaned_data['valor']
        if valor <= 0:
            raise forms.ValidationError(
                'El valor del gasto debe ser mayor que cero.'
            )
        return valor

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
            'valor': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01',
            }),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta_pago'].queryset = CuentaFinanciera.objects.filter(
            activa=True
        )

    def clean_valor(self):
        valor = self.cleaned_data['valor']
        if valor <= 0:
            raise forms.ValidationError(
                'El valor del pago debe ser mayor que cero.'
            )
        return valor

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
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0.01',
            'step': '0.01',
        }),
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
