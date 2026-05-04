
"""
Vistas del módulo de gestión de la academia.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models.manager import BaseManager
from django.shortcuts import render, redirect
from django.contrib import messages

from alumnos.models import Alumno
from planes.models import Plan, Suscripcion
from pagos.models import Pago

from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .forms import ValidarPagoForm

from .forms import (
    UsuarioAlumnoForm,
    AlumnoForm,
    PlanForm,
    SuscripcionForm,
    PagoForm,
)

from datetime import timedelta
from django.utils import timezone
from notificaciones.models import Notificacion


@staff_member_required
def dashboard(request):
    alumnos = Alumno.objects.all()

    for alumno in alumnos:
        alumno.actualizar_estado()

    total_alumnos = alumnos.count()
    total_planes = Plan.objects.count()
    total_suscripciones = Suscripcion.objects.count()
    total_pagos = Pago.objects.count()

    hoy = timezone.now().date()
    limite = hoy + timedelta(days=7)

    pagos_pendientes = Pago.objects.filter(
        estado='PENDIENTE'
    ).select_related('alumno__user')[:5]

    suscripciones_por_vencer = Suscripcion.objects.filter(
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=limite,
        estado='ACTIVA'
    ).select_related('alumno__user', 'plan')[:5]

    alumnos_vencidos = Alumno.objects.filter(
        estado='VENCIDO'
    ).select_related('user')[:5]

    ultimas_notificaciones: BaseManager[Notificacion] = Notificacion.objects.select_related(
        'usuario'
    ).order_by('-fecha_creacion')[:5]

    context = {
        'total_alumnos': total_alumnos,
        'total_planes': total_planes,
        'total_suscripciones': total_suscripciones,
        'total_pagos': total_pagos,
        'pagos_pendientes': pagos_pendientes,
        'suscripciones_por_vencer': suscripciones_por_vencer,
        'alumnos_vencidos': alumnos_vencidos,
        'ultimas_notificaciones': ultimas_notificaciones,
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
    suscripciones = Suscripcion.objects.select_related(
        'alumno__user', 'plan').all()
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


@staff_member_required
def validar_pago(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)

    if pago.estado != 'PENDIENTE':
        messages.warning(request, 'Este pago ya fue validado.')
        return redirect('gestion:lista_pagos')

    if request.method == 'POST':
        form = ValidarPagoForm(request.POST, instance=pago)

        if form.is_valid():
            pago = form.save(commit=False)
            pago.validado_por = request.user
            pago.fecha_validacion = timezone.now()

            if pago.estado == 'APROBADO':
                suscripcion = pago.suscripcion
                hoy = timezone.now().date()

                # fecha_base = suscripcion.fecha_vencimiento or hoy
                if suscripcion.estado == 'PENDIENTE_PAGO':
                    fecha_base = hoy

                else:
                    fecha_base = suscripcion.fecha_vencimiento or hoy

                suscripcion.fecha_inicio = fecha_base
                suscripcion.fecha_vencimiento = (
                    fecha_base + timedelta(days=suscripcion.plan.duracion_dias)
                )

                if suscripcion.fecha_vencimiento < hoy:
                    suscripcion.estado = 'VENCIDA'
                    pago.alumno.estado = 'VENCIDO'
                    messages.warning(
                        request,
                        'Pago aprobado, pero el alumno aún queda con mensualidades vencidas.'
                    )
                else:
                    suscripcion.estado = 'ACTIVA'
                    pago.alumno.estado = 'ACTIVO'
                    messages.success(
                        request,
                        'Pago aprobado y suscripción actualizada correctamente.'
                    )

                suscripcion.save()
                pago.alumno.save()

            elif pago.estado == 'RECHAZADO':
                messages.warning(request, 'Pago rechazado correctamente.')

            pago.save()
            return redirect('gestion:lista_pagos')

    else:
        form = ValidarPagoForm(instance=pago)

    return render(request, 'gestion/validar_pago.html', {
        'form': form,
        'pago': pago,
    })


@staff_member_required
def editar_alumno(request, alumno_id):
    alumno = get_object_or_404(Alumno, id=alumno_id)

    if request.method == 'POST':
        form = AlumnoForm(request.POST, instance=alumno)
        if form.is_valid():
            form.save()
            messages.success(request, 'Alumno actualizado correctamente.')
            return redirect('gestion:lista_alumnos')
    else:
        form = AlumnoForm(instance=alumno)

    return render(request, 'gestion/formulario.html', {
        'form': form,
        'titulo': 'Editar alumno',
        'cancelar_url': 'gestion:lista_alumnos'
    })


@staff_member_required
def eliminar_alumno(request, alumno_id):
    alumno = get_object_or_404(Alumno, id=alumno_id)

    if request.method == 'POST':
        alumno.delete()
        messages.success(request, 'Alumno eliminado correctamente.')
        return redirect('gestion:lista_alumnos')

    return render(request, 'gestion/confirmar_eliminar.html', {
        'objeto': alumno,
        'cancelar_url': 'gestion:lista_alumnos'
    })


@staff_member_required
def editar_plan(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)

    if request.method == 'POST':
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, 'Plan actualizado correctamente.')
            return redirect('gestion:lista_planes')
    else:
        form = PlanForm(instance=plan)

    return render(request, 'gestion/formulario.html', {
        'form': form,
        'titulo': 'Editar plan',
        'cancelar_url': 'gestion:lista_planes'
    })


@staff_member_required
def eliminar_plan(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)

    if request.method == 'POST':
        plan.delete()
        messages.success(request, 'Plan eliminado correctamente.')
        return redirect('gestion:lista_planes')

    return render(request, 'gestion/confirmar_eliminar.html', {
        'objeto': plan,
        'cancelar_url': 'gestion:lista_planes'
    })


@staff_member_required
def editar_suscripcion(request, suscripcion_id):
    suscripcion = get_object_or_404(Suscripcion, id=suscripcion_id)

    if request.method == 'POST':
        form = SuscripcionForm(request.POST, instance=suscripcion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Suscripción actualizada correctamente.')
            return redirect('gestion:lista_suscripciones')
    else:
        form = SuscripcionForm(instance=suscripcion)

    return render(request, 'gestion/formulario.html', {
        'form': form,
        'titulo': 'Editar suscripción',
        'cancelar_url': 'gestion:lista_suscripciones'
    })


@staff_member_required
def eliminar_suscripcion(request, suscripcion_id):
    suscripcion = get_object_or_404(Suscripcion, id=suscripcion_id)

    if request.method == 'POST':
        suscripcion.delete()
        messages.success(request, 'Suscripción eliminada correctamente.')
        return redirect('gestion:lista_suscripciones')

    return render(request, 'gestion/confirmar_eliminar.html', {
        'objeto': suscripcion,
        'cancelar_url': 'gestion:lista_suscripciones'
    })
