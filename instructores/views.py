from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from .forms import SolicitudRegistroProfesorForm
from .models import SolicitudRegistroProfesor


def registro_profesor(request):
    form = SolicitudRegistroProfesorForm(
        request.POST or None,
        request.FILES or None,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error(
                None,
                'Ya existe una solicitud pendiente con este documento o usuario.',
            )
        else:
            messages.success(
                request,
                'Tu registro como profesor fue enviado y quedó pendiente de aprobación.',
            )
            return redirect('instructores:registro_profesor_exitoso')
    return render(request, 'instructores/registro_profesor.html', {'form': form})


def registro_profesor_exitoso(request):
    return render(request, 'instructores/registro_profesor_exitoso.html')
