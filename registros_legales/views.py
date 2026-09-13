from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

from alumnos.models import Alumno
from instructores.models import Instructor

from .forms import (
    MENSAJE_REGISTRO_PENDIENTE,
    RegistroLegalEstudianteForm,
    contactos_repetidos,
)
from .models import RegistroLegalEstudiante


@require_POST
def validar_datos_registro(request):
    documento = request.POST.get('documento', '').strip()
    celular = request.POST.get('celular', '').strip()
    correo = request.POST.get('correo', '').strip()
    username = request.POST.get('usuario_solicitado', '').strip()
    errores = {}

    registro_existente = None
    if documento:
        registro_existente = RegistroLegalEstudiante.objects.filter(
            documento__iexact=documento
        ).exclude(
            estado=RegistroLegalEstudiante.Estados.RECHAZADO
        ).order_by('-creado').first()

    if (
        registro_existente
        and registro_existente.estado
        == RegistroLegalEstudiante.Estados.PENDIENTE_VALIDACION
    ):
        errores['documento'] = MENSAJE_REGISTRO_PENDIENTE
    elif documento and (
        registro_existente
        or Alumno.objects.filter(documento=documento).exists()
        or Instructor.objects.filter(documento=documento).exists()
    ):
        errores['documento'] = (
            'Ya existe un estudiante o registro con este documento, '
            'o está asignado a un instructor.'
        )

    if username:
        if get_user_model().objects.filter(username__iexact=username).exists():
            errores['usuario_solicitado'] = 'Este nombre de usuario ya está en uso.'
        elif RegistroLegalEstudiante.objects.filter(
            usuario_solicitado__iexact=username,
        ).exclude(estado=RegistroLegalEstudiante.Estados.RECHAZADO).exists():
            errores['usuario_solicitado'] = (
                'Este nombre de usuario ya está reservado por otro registro.'
            )

    advertencias = contactos_repetidos(correo, celular)
    return JsonResponse({
        'valido': not errores,
        'errores': errores,
        'advertencias': advertencias,
        'requiere_confirmacion_contacto': bool(advertencias),
    })


def registro_publico(request):

    if request.method == 'POST':

        form = RegistroLegalEstudianteForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            registro = form.save(commit=False)

            registro.texto_consentimiento = (
                'Consentimiento aceptado digitalmente.'
            )

            registro.ip_firma = get_client_ip(request)
            registro.estado = RegistroLegalEstudiante.Estados.PENDIENTE_VALIDACION
            try:
                with transaction.atomic():
                    registro.save()
            except IntegrityError:
                if RegistroLegalEstudiante.objects.filter(
                    documento__iexact=registro.documento,
                    estado=RegistroLegalEstudiante.Estados.PENDIENTE_VALIDACION,
                ).exists():
                    form.add_error('documento', MENSAJE_REGISTRO_PENDIENTE)
                else:
                    form.add_error(
                        None,
                        'No se pudo guardar porque ya existe un registro con '
                        'estos datos. Revisa el documento y el usuario.',
                    )
            else:
                messages.success(
                    request,
                    'Registro enviado correctamente. Quedará pendiente de validación por un administrador.'
                )

                return redirect('registro_exitoso')

    else:

        form = RegistroLegalEstudianteForm()

    return render(
        request,
        'registros_legales/registro_publico.html',
        {
            'form': form
        }
    )


def registro_exitoso(request):

    return render(
        request,
        'registros_legales/registro_exitoso.html'
    )


def get_client_ip(request):

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]

    else:
        ip = request.META.get('REMOTE_ADDR')

    return ip
