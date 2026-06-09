from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from clases.models import ClaseProgramada
from .forms import ClaseCortesiaForm
from .models import ConsentimientoFirmado, ClaseCortesia
from django.contrib.admin.views.decorators import staff_member_required

CONSENTIMIENTO_ADULTO = """
Declaro que participo voluntariamente en las actividades deportivas
y entiendo los riesgos asociados a la práctica física.
"""

CONSENTIMIENTO_MENOR = """
Como acudiente autorizo la participación del menor en las actividades
deportivas desarrolladas por la academia.
"""


def registrar_cortesia(request, clase_id):

    clase = get_object_or_404(
        ClaseProgramada,
        id=clase_id,
        activa=True
    )

    if request.method == 'POST':

        form = ClaseCortesiaForm(request.POST)

        if form.is_valid():

            tipo_persona = form.cleaned_data['tipo_persona']

            if tipo_persona == 'MENOR':
                texto = CONSENTIMIENTO_MENOR
            else:
                texto = CONSENTIMIENTO_ADULTO

            consentimiento = ConsentimientoFirmado.objects.create(
                tipo=tipo_persona,
                nombre_estudiante=(
                    f"{form.cleaned_data['nombres']} "
                    f"{form.cleaned_data['apellidos']}"
                ),
                documento_estudiante=form.cleaned_data['documento'],
                nombre_acudiente=form.cleaned_data.get('nombre_acudiente'),
                documento_acudiente=form.cleaned_data.get(
                    'documento_acudiente'),
                texto_aceptado=texto,
                firma_base64=form.cleaned_data['firma_base64'],
                fecha_firma=timezone.now(),
            )

            cortesia = form.save(commit=False)

            cortesia.clase = clase
            cortesia.consentimiento = consentimiento

            cortesia.save()

            messages.success(
                request,
                'Clase de cortesía registrada correctamente.'
            )

            return redirect('gestion:horario_clases')

    else:

        form = ClaseCortesiaForm()

    return render(
        request,
        'cortesias/registrar_cortesia.html',
        {
            'form': form,
            'clase': clase,
            'consentimiento_adulto': CONSENTIMIENTO_ADULTO,
            'consentimiento_menor': CONSENTIMIENTO_MENOR,
        }
    )


@staff_member_required
def lista_cortesias(request):

    cortesias = ClaseCortesia.objects.select_related(
        'clase'
    ).order_by(
        '-fecha_registro'
    )

    total_cortesias = cortesias.count()

    total_contactados = cortesias.filter(
        contactado=True
    ).count()

    total_convertidos = cortesias.filter(
        se_convirtio=True
    ).count()

    return render(
        request,
        'cortesias/lista_cortesias.html',
        {
            'cortesias': cortesias,
            'total_cortesias': total_cortesias,
            'total_contactados': total_contactados,
            'total_convertidos': total_convertidos,
        }
    )
