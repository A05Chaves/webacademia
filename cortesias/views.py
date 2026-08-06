from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from clases.models import ClaseProgramada
from .forms import ClaseCortesiaForm, ConfiguracionSeguimientoCortesiaForm
from .models import (
    ClaseCortesia, ConfiguracionSeguimientoCortesia, ConsentimientoFirmado,
)
from .services import (
    cortesias_elegibles_para_correo, enviar_seguimiento_cortesias,
    sincronizar_conversiones_cortesias,
)


DIAS_SEMANA = {
    'LUNES': 0,
    'MARTES': 1,
    'MIERCOLES': 2,
    'JUEVES': 3,
    'VIERNES': 4,
    'SABADO': 5,
    'DOMINGO': 6,
}


def puede_gestionar_cortesias(user):
    return user.is_authenticated and (
        user.is_staff or hasattr(user, 'perfil_instructor')
    )


def proxima_fecha_clase(clase):
    ahora = timezone.localtime()
    dias_hasta_clase = (DIAS_SEMANA[clase.dia] - ahora.weekday()) % 7
    if dias_hasta_clase == 0 and ahora.time() >= clase.hora_inicio:
        dias_hasta_clase = 7
    return ahora.date() + timedelta(days=dias_hasta_clase)

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
def registrar_cortesia(request, clase_id=None):
    clase = None
    if clase_id is not None:
        clase = get_object_or_404(ClaseProgramada, id=clase_id, activa=True)
    tipo_solicitado = request.GET.get('tipo', '').upper()
    tipos_validos = {
        ClaseCortesia.TiposPersona.ADULTO,
        ClaseCortesia.TiposPersona.MENOR,
    }
    if tipo_solicitado not in tipos_validos:
        tipo_solicitado = None

    if (
        tipo_solicitado
        and clase
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
            publico_objetivo=clase.publico_objetivo if clase else None,
        )

        if form.is_valid():

            tipo_persona = form.cleaned_data['tipo_persona']
            es_menor_legal = form.cleaned_data['edad'] < 18

            if es_menor_legal:
                texto = CONSENTIMIENTO_MENOR
            else:
                texto = CONSENTIMIENTO_ADULTO

            consentimiento = ConsentimientoFirmado.objects.create(
                tipo=(
                    ConsentimientoFirmado.Tipos.MENOR
                    if es_menor_legal
                    else ConsentimientoFirmado.Tipos.ADULTO
                ),
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

            if clase:
                cortesia.fecha_clase = proxima_fecha_clase(clase)

            cortesia.save()

            if not clase:
                request.session['solicitud_cortesia_id'] = cortesia.id
                messages.success(
                    request,
                    'Consentimiento registrado. Ahora selecciona uno de los cuadros de color del horario.'
                )
                return redirect(
                    f"{reverse('gestion:horario_clases')}"
                    f"?cortesia={tipo_persona}&solicitud={cortesia.id}"
                )

            messages.success(
                request,
                'Clase de cortesía registrada correctamente.'
            )

            return redirect('gestion:home_publica')

    else:

        form = ClaseCortesiaForm(
            tipo_persona=tipo_solicitado,
            publico_objetivo=clase.publico_objetivo if clase else None,
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
                if tipo_solicitado and clase
                else reverse('gestion:home_publica')
            ),
        }
    )


@transaction.atomic
def seleccionar_clase_cortesia(request, cortesia_id, clase_id):
    if request.method != 'POST':
        return HttpResponseForbidden('La clase debe seleccionarse desde el horario.')

    if request.session.get('solicitud_cortesia_id') != cortesia_id:
        return HttpResponseForbidden('Esta solicitud no corresponde a la sesión actual.')

    cortesia = get_object_or_404(
        ClaseCortesia.objects.select_related('consentimiento'),
        id=cortesia_id,
        clase__isnull=True,
    )
    clase = get_object_or_404(ClaseProgramada, id=clase_id, activa=True)
    if clase.publico_objetivo not in {
        ClaseProgramada.PublicosObjetivo.TODOS,
        cortesia.tipo_persona,
    }:
        messages.error(request, 'La clase no corresponde a la edad del participante.')
        return redirect(
            f"{reverse('gestion:horario_clases')}"
            f"?cortesia={cortesia.tipo_persona}&solicitud={cortesia.id}"
        )

    cortesia.clase = clase
    cortesia.fecha_clase = proxima_fecha_clase(clase)
    cortesia.save(update_fields=['clase', 'fecha_clase'])
    request.session.pop('solicitud_cortesia_id', None)
    messages.success(
        request,
        f'Clase de cortesía agendada para el {cortesia.fecha_clase:%d/%m/%Y}.'
    )
    return redirect('gestion:home_publica')


@user_passes_test(puede_gestionar_cortesias)
def lista_cortesias(request):

    sincronizar_conversiones_cortesias()
    configuracion = ConfiguracionSeguimientoCortesia.cargar()

    if request.method == 'POST':
        form_campana = ConfiguracionSeguimientoCortesiaForm(
            request.POST,
            request.FILES,
            instance=configuracion,
        )
        if form_campana.is_valid():
            configuracion = form_campana.save()
            if request.POST.get('accion') == 'enviar':
                enviados, fallidos = enviar_seguimiento_cortesias(
                    configuracion,
                    request,
                )
                if enviados:
                    messages.success(request, f'Se enviaron {enviados} correos de seguimiento.')
                elif not fallidos:
                    messages.info(request, 'No hay personas que cumplan ahora las condiciones de envío.')
                if fallidos:
                    messages.error(request, f'No fue posible enviar {fallidos} correos.')
            else:
                messages.success(request, 'Configuración de seguimiento guardada.')
            return redirect('cortesias:lista_cortesias')
    else:
        form_campana = ConfiguracionSeguimientoCortesiaForm(instance=configuracion)

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

    total_agendadas = cortesias.filter(
        clase__isnull=False,
        fecha_clase__gte=timezone.localdate(),
    ).count()
    total_elegibles_correo = cortesias_elegibles_para_correo(configuracion).count()

    return render(
        request,
        'cortesias/lista_cortesias.html',
        {
            'cortesias': cortesias,
            'total_cortesias': total_cortesias,
            'total_contactados': total_contactados,
            'total_convertidos': total_convertidos,
            'total_agendadas': total_agendadas,
            'form_campana': form_campana,
            'total_elegibles_correo': total_elegibles_correo,
        }
    )


@user_passes_test(puede_gestionar_cortesias)
def cambiar_contactado(request, cortesia_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Esta acción requiere confirmación.')
    cortesia = get_object_or_404(ClaseCortesia, id=cortesia_id)
    cortesia.contactado = not cortesia.contactado
    cortesia.fecha_contacto = timezone.now() if cortesia.contactado else None
    cortesia.contactado_por = request.user if cortesia.contactado else None
    cortesia.save(update_fields=['contactado', 'fecha_contacto', 'contactado_por'])
    messages.success(
        request,
        'Contacto registrado.' if cortesia.contactado else 'Se retiró la marca de contacto.',
    )
    return redirect('cortesias:lista_cortesias')


@user_passes_test(puede_gestionar_cortesias)
def cambiar_asistencia(request, cortesia_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Esta acción requiere confirmación.')
    cortesia = get_object_or_404(ClaseCortesia, id=cortesia_id)
    cortesia.asistio = not cortesia.asistio
    cortesia.fecha_confirmacion_asistencia = timezone.now() if cortesia.asistio else None
    cortesia.asistencia_confirmada_por = request.user if cortesia.asistio else None
    cortesia.save(update_fields=[
        'asistio', 'fecha_confirmacion_asistencia', 'asistencia_confirmada_por',
    ])
    messages.success(
        request,
        'Asistencia registrada.' if cortesia.asistio else 'Se retiró la marca de asistencia.',
    )
    return redirect('cortesias:lista_cortesias')
