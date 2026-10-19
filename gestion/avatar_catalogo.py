from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from alumnos.models import Alumno
from config.file_validation import validate_image
from .decorators import administrador_required
from .models import AvatarCatalogo, ArticuloAvatar, ConfiguracionAvatar, MovimientoMonedas


class CatalogoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'form-check-input' if isinstance(campo.widget, forms.CheckboxInput) else 'form-control'

    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        if imagen and hasattr(imagen, 'content_type'):
            validate_image(imagen)
        return imagen


class AvatarForm(CatalogoForm):
    class Meta:
        model = AvatarCatalogo
        fields = ['nombre', 'descripcion', 'publico', 'precio', 'imagen', 'activo']


class ArticuloForm(CatalogoForm):
    class Meta:
        model = ArticuloAvatar
        fields = ['nombre', 'descripcion', 'tipo', 'publico', 'precio', 'avatar', 'requisito', 'imagen', 'activo']

    def clean(self):
        datos = super().clean()
        requisito = datos.get('requisito')
        if requisito and self.instance.pk:
            vistos = {self.instance.pk}
            while requisito:
                if requisito.pk in vistos:
                    self.add_error('requisito', 'Las mejoras no pueden tener requisitos circulares.')
                    break
                vistos.add(requisito.pk)
                requisito = requisito.requisito
        return datos


@administrador_required
def panel(request):
    configuracion, _ = ConfiguracionAvatar.objects.get_or_create(pk=1)
    alumnos = Alumno.objects.select_related('user', 'user__billetera_monedas').order_by('user__first_name', 'user__last_name', 'pk')
    consulta = request.GET.get('q', '').strip()
    if consulta:
        alumnos = alumnos.filter(Q(user__first_name__icontains=consulta) | Q(user__last_name__icontains=consulta) | Q(documento__icontains=consulta) | Q(user__username__icontains=consulta))
    pagina = Paginator(alumnos, 20).get_page(request.GET.get('pagina'))
    hoy = timezone.localdate()
    for alumno in pagina:
        nacimiento = alumno.fecha_nacimiento
        edad = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)) if nacimiento else None
        alumno.publico_avatar = 'Sin fecha de nacimiento' if edad is None else ('Niños' if edad < configuracion.edad_adulto else 'Adultos')
        billetera = getattr(alumno.user, 'billetera_monedas', None)
        alumno.saldo_avatar = billetera.saldo if billetera else 0
    return render(request, 'gestion/avatares_panel.html', {
        'alumnos': pagina, 'q': consulta, 'configuracion_avatar': configuracion,
        'total_estudiantes': Alumno.objects.count(),
        'total_monedas': Alumno.objects.aggregate(total=Sum('user__billetera_monedas__saldo'))['total'] or 0,
        'avatares': AvatarCatalogo.objects.all(), 'articulos': ArticuloAvatar.objects.select_related('avatar', 'requisito'),
        'movimientos': MovimientoMonedas.objects.select_related('billetera__usuario', 'registrado_por')[:30],
    })


@administrador_required
def editar(request, tipo, pk=None):
    clases = {'avatar': (AvatarCatalogo, AvatarForm), 'articulo': (ArticuloAvatar, ArticuloForm)}
    from django.http import Http404
    if tipo not in clases:
        raise Http404
    modelo, formulario = clases[tipo]
    instancia = get_object_or_404(modelo, pk=pk) if pk else None
    form = formulario(request.POST or None, request.FILES or None, instance=instancia)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Catálogo actualizado. Los saldos de monedas no se modificaron.')
        return redirect('gestion:avatares_panel')
    return render(request, 'gestion/avatares_form.html', {'form': form, 'titulo': ('Editar ' if pk else 'Crear ') + ('avatar' if tipo == 'avatar' else 'artículo o mejora')})


@administrador_required
def configurar(request):
    configuracion, _ = ConfiguracionAvatar.objects.get_or_create(pk=1)
    class ConfigForm(forms.ModelForm):
        class Meta:
            model = ConfiguracionAvatar
            fields = ['edad_adulto']
    form = ConfigForm(request.POST or None, instance=configuracion)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Edad de clasificación actualizada.')
        return redirect('gestion:avatares_panel')
    return render(request, 'gestion/avatares_form.html', {'form': form, 'titulo': 'Configuración de avatares'})
