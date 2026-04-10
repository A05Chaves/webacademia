from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages

from alumnos.models import Alumno
from planes.models import Plan, Suscripcion
from pagos.models import Pago

from .forms import (
    UsuarioAlumnoForm,
    AlumnoForm,
    PlanForm,
    SuscripcionForm,
    PagoForm,
)


@staff_member_required
def dashboard(request):
    total_alumnos = Alumno.objects.count()
    total_planes = Plan.objects.count()
    total_suscripciones = Suscripcion.objects.count()
    total_pagos = Pago.objects.count()

    context = {
        'total_alumnos': total_alumnos,
        'total_planes': total_planes,
        'total_suscripciones': total_suscripciones,
        'total_pagos': total_pagos,
    }
    return render(request, 'gestion/dashboard.html', context)


@staff_member_required
def lista_alumnos(request):
    alumnos = Alumno.objects.select_related('user').all()
    return render(request, 'gestion/lista_alumnos.html', {'alumnos': alumnos})


@staff_member_required
def crear_alumno(request):
    if request.method == 'POST':
        usuario_form = UsuarioAlumnoForm(request.POST)
        alumno_form = AlumnoForm(request.POST)

        if usuario_form.is_valid() and alumno_form.is_valid():
            user = usuario_form.save()
            alumno = alumno_form.save(commit=False)
            alumno.user = user
            alumno.save()

            messages.success(request, 'Alumno creado correctamente.')
            return redirect('gestion:lista_alumnos')
    else:
        usuario_form = UsuarioAlumnoForm()
        alumno_form = AlumnoForm()

    context = {
        'usuario_form': usuario_form,
        'alumno_form': alumno_form,
    }
    return render(request, 'gestion/crear_alumno.html', context)


@staff_member_required
def lista_planes(request):
    planes = Plan.objects.all()
    return render(request, 'gestion/lista_planes.html', {'planes': planes})


@staff_member_required
def crear_plan(request):
    if request.method == 'POST':
        form = PlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Plan creado correctamente.')
            return redirect('gestion:lista_planes')
    else:
        form = PlanForm()

    return render(request, 'gestion/crear_plan.html', {'form': form})


@staff_member_required
def lista_suscripciones(request):
    suscripciones = Suscripcion.objects.select_related('alumno__user', 'plan').all()
    return render(request, 'gestion/lista_suscripciones.html', {'suscripciones': suscripciones})


@staff_member_required
def crear_suscripcion(request):
    if request.method == 'POST':
        form = SuscripcionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Suscripción creada correctamente.')
            return redirect('gestion:lista_suscripciones')
    else:
        form = SuscripcionForm()

    return render(request, 'gestion/crear_suscripcion.html', {'form': form})


@staff_member_required
def lista_pagos(request):
    pagos = Pago.objects.select_related(
        'alumno__user',
        'suscripcion',
        'metodo_qr',
        'validado_por'
    ).all()
    return render(request, 'gestion/lista_pagos.html', {'pagos': pagos})


@staff_member_required
def crear_pago(request):
    if request.method == 'POST':
        form = PagoForm(request.POST, request.FILES)
        if form.is_valid():
            pago = form.save(commit=False)

            if pago.estado in ['APROBADO', 'RECHAZADO']:
                pago.validado_por = request.user

            pago.save()
            messages.success(request, 'Pago registrado correctamente.')
            return redirect('gestion:lista_pagos')
    else:
        form = PagoForm()

    return render(request, 'gestion/crear_pago.html', {'form': form})