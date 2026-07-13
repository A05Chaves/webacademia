from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from clases.models import ClaseProgramada
from .forms import ClaseCortesiaForm
from .models import ConsentimientoFirmado, ClaseCortesia
from django.contrib.admin.views.decorators import staff_member_required

CONSENTIMIENTO_ADULTO = """
Declaro que participo voluntariamente en las actividades deportivas
y entiendo los riesgos asociados a la práctica física. Confirmo que la
información suministrada es correcta y firmo personalmente este consentimiento.
"""

CONSENTIMIENTO_MENOR = """
Como padre, madre o acudiente responsable autorizo la participación del menor
en las actividades deportivas desarrolladas por la academia, declaro que la
información suministrada es correcta y firmo este consentimiento en su nombre.
"""


@transaction.atomic
def registrar_cortesia(request, clase_id):

    clase = get_object_or_404(
        ClaseProgramada,
        id=clase_id,
        activa=True
    )
    tipo_solicitado = request.GET.get('tipo', '').upper()
    tipos_validos = {
        ClaseCortesia.TiposPersona.ADULTO,
        ClaseCortesia.TiposPersona.MENOR,
    }
    if tipo_solicitado not in tipos_validos:
        tipo_solicitado = None

    if (
        tipo_solicitado
        and clase.publico_objetivo != ClaseProgramada.PublicosObjetivo.TODOS
        and clase.publico_objetivo != tipo_solicitado
    ):
        messages.error(
            request,
            'La clase seleccionada no corresponde al participante indicado.'
        )
        return redirect(
            f"{reverse('gestion:horario_clases')}?cortesia={tipo_solicitado}"
        )

    if request.method == 'POST':

        form = ClaseCortesiaForm(
            request.POST,
            tipo_persona=tipo_solicitado,
            publico_objetivo=clase.publico_objetivo,
        )

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

            return redirect('gestion:home_publica')

    else:

        form = ClaseCortesiaForm(
            tipo_persona=tipo_solicitado,
            publico_objetivo=clase.publico_objetivo,
        )

    return render(
        request,
        'cortesias/registrar_cortesia.html',
        {
            'form': form,
            'clase': clase,
            'consentimiento_adulto': CONSENTIMIENTO_ADULTO,
            'consentimiento_menor': CONSENTIMIENTO_MENOR,
            'tipo_solicitado': tipo_solicitado,
            'cancelar_url': (
                f"{reverse('gestion:horario_clases')}?cortesia={tipo_solicitado}"
                if tipo_solicitado
                else reverse('gestion:horario_clases')
            ),
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
