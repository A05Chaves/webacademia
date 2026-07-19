from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

from alumnos.models import Alumno
from instructores.models import Instructor

from .forms import RegistroLegalEstudianteForm
from .models import RegistroLegalEstudiante


@require_POST
def validar_datos_registro(request):
    documento = request.POST.get('documento', '').strip()
    correo = request.POST.get('correo', '').strip()
    celular = request.POST.get('celular', '').strip()
    username = request.POST.get('usuario_solicitado', '').strip()
    errores = {}

    if documento and (
        RegistroLegalEstudiante.objects.filter(documento=documento).exists()
        or Alumno.objects.filter(documento=documento).exists()
        or Instructor.objects.filter(documento=documento).exists()
    ):
        errores['documento'] = (
            'Ya existe un estudiante o registro con este documento, '
            'o está asignado a un instructor.'
        )

    if correo and RegistroLegalEstudiante.objects.filter(
        correo__iexact=correo
    ).exists():
        errores['correo'] = 'Ya existe un registro con este correo.'

    if celular and RegistroLegalEstudiante.objects.filter(
        celular=celular
    ).exists():
        errores['celular'] = 'Ya existe un registro con este celular.'

    if username:
        if get_user_model().objects.filter(username__iexact=username).exists():
            errores['usuario_solicitado'] = 'Este nombre de usuario ya está en uso.'
        elif RegistroLegalEstudiante.objects.filter(
            usuario_solicitado__iexact=username,
        ).exclude(estado=RegistroLegalEstudiante.Estados.RECHAZADO).exists():
            errores['usuario_solicitado'] = (
                'Este nombre de usuario ya está reservado por otro registro.'
            )

    return JsonResponse({'valido': not errores, 'errores': errores})


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
            registro.save()

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
