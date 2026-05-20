from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import RegistroLegalEstudianteForm
from .models import RegistroLegalEstudiante
from .services import crear_alumno_desde_registro


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

            registro.save()

            if request.user.is_authenticated and request.user.is_staff:

                alumno, password_temporal, error = crear_alumno_desde_registro(
                    registro
                )

                if error:
                    messages.error(request, error)
                    return redirect('registro_exitoso')

                registro.estado = RegistroLegalEstudiante.Estados.APROBADO
                registro.save()

                messages.success(
                    request,
                    f'Alumno creado correctamente. Usuario: {registro.documento} | Clave temporal: {password_temporal}'
                )

            else:

                messages.success(
                    request,
                    'Registro enviado correctamente. Quedará pendiente de validación.'
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
