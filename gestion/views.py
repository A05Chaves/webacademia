
"""
Vistas del módulo de gestión de la academia.
from registros_legales.services import crear_alumno_desde_registro
"""

from urllib.parse import urlparse, parse_qs
import calendar
import hashlib
from .forms import ConfiguracionHomeForm
from registros_legales.services import (
    crear_alumno_desde_registro,
    enviar_correo_bienvenida_alumno,
)
from reportlab.lib.utils import ImageReader
from io import BytesIO
import base64
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.http import JsonResponse, Http404
from .forms import CambioPasswordObligatorioForm, CambiarUsuarioForm
from django.contrib.auth import update_session_auth_hash
import random
import json
import secrets
from django.contrib.auth.hashers import make_password
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models.manager import BaseManager
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages

from alumnos.models import Alumno
from planes.models import Plan, Suscripcion
from pagos.models import (
    AcademiaCompetidora, AplicacionPromocion, CategoriaEvento, Evento,
    InscripcionEvento, MetodoPagoQR, Pago, Promocion,
)
from pagos.services import (
    enviar_comprobante_pago, generar_pdf_comprobante_pago,
    marcar_posible_duplicado,
)
from datetime import timedelta
from django.shortcuts import get_object_or_404
from .forms import ValidarPagoForm

from .forms import (
    AplicarPromocionForm,
    CategoriaEventoForm,
    EditarInscripcionEventoForm,
    EventoForm,
    InscripcionEventoForm,
    PromocionForm,
    UsuarioAlumnoForm,
    UsuarioAlumnoEditForm,
    AlumnoForm,
    PlanForm,
    SuscripcionForm,
    PagoForm,

)

from django.utils import timezone
from notificaciones.models import Notificacion
from instructores.models import Instructor

from datetime import datetime, time
from clases.models import ClaseProgramada, AsistenciaClase
from .forms import ClaseProgramadaForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.db.models import Count, Q
from django.db import IntegrityError, models, transaction

from django.contrib.auth import authenticate
from django.views.decorators.http import require_POST
from django.templatetags.static import static
from .models import DiaHorario, HoraHorario, SesionTV, estado_tv_inicial
from .forms import DiaHorarioForm, HoraHorarioForm

from .forms import PagoAlumnoForm
from django.core.mail import send_mail
from django.conf import settings

from finanzas.models import CategoriaFinanciera, CuentaFinanciera, MovimientoFinanciero, PagoProgramado
from .forms import GastoForm
from .forms import CuentaFinancieraForm, PagoProgramadoForm, TransferenciaForm
from django.db.models import Sum
from registros_legales.models import RegistroLegalEstudiante
from .models import ConfiguracionHome
from alumnos.models import Alumno
from django.contrib.auth import get_user_model
User = get_user_model()


def plan_permite_disciplina(plan, disciplina):
    """Valida la disciplina usando la configuración vigente del plan."""
    permisos = {
        ClaseProgramada.Disciplinas.JIU_JITSU: plan.permite_jiu_jitsu,
        ClaseProgramada.Disciplinas.MUAY_THAI: plan.permite_muay_thai,
        ClaseProgramada.Disciplinas.MMA: plan.permite_mma,
        ClaseProgramada.Disciplinas.MMA_MUAYTHAI: (
            plan.permite_mma or plan.permite_muay_thai
        ),
        ClaseProgramada.Disciplinas.OTRA: True,
    }

    # Los planes creados antes de estos indicadores quedaron con los tres
    # valores en False durante la migración. Se conserva su acceso hasta que
    # un administrador configure explícitamente sus disciplinas.
    sin_configuracion = not any((
        plan.permite_jiu_jitsu,
        plan.permite_muay_thai,
        plan.permite_mma,
    ))
    return sin_configuracion or permisos.get(disciplina, False)

# CONVIERTE VIDEOS YOUTUBE


def convertir_youtube_embed(url):

    if not url:
        return ""

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # Si existe video, usar el video primero
    if "v" in query:

        video_id = query["v"][0]

        return (
            f"https://www.youtube.com/embed/{video_id}"
            f"?autoplay=1&mute=1&playsinline=1&rel=0"
        )

    # Playlist normal
    if "list" in query:

        playlist_id = query["list"][0]

        return (
            f"https://www.youtube.com/embed/videoseries"
            f"?list={playlist_id}"
        )

    return url

# VISTA HOME DEL PROGRAMA


def home_publica(request):

    ahora = timezone.localtime()
    hoy = ahora.date()
    hora_actual = ahora.time()

    dias_semana = {
        0: 'LUNES',
        1: 'MARTES',
        2: 'MIERCOLES',
        3: 'JUEVES',
        4: 'VIERNES',
        5: 'SABADO',
        6: 'DOMINGO',
    }

    dia_actual = dias_semana[ahora.weekday()]

    clases_hoy = ClaseProgramada.objects.filter(
        activa=True,
        dia=dia_actual
    ).order_by('hora_inicio')

    # El panel "Entrenando ahora" solo muestra la clase que está ocurriendo.
    # La ventana anticipada de 20 minutos se usa únicamente para confirmar.
    clase_en_ventana = clases_hoy.filter(
        hora_inicio__lte=hora_actual,
        hora_fin__gt=hora_actual,
    ).order_by('hora_inicio')[:1]

    asistencias_hoy = AsistenciaClase.objects.filter(
        fecha_clase=hoy,
        estado=AsistenciaClase.Estados.CONFIRMADA,
        clase__in=clase_en_ventana,
    ).select_related(
        'alumno__user',
        'clase'
    ).order_by('-fecha_confirmacion')[:10]

    config_home = ConfiguracionHome.objects.filter(
        activo=True
    ).first()

    promo_embed = ""
    playlist_embed = ""

    if config_home:
        promo_embed = convertir_youtube_embed(
            config_home.video_promo_url
        )

        playlist_embed = convertir_youtube_embed(
            config_home.playlist_youtube_url
        )

    clase_confirmable = None

    for clase in clases_hoy:

        inicio_clase = timezone.make_aware(
            datetime.combine(hoy, clase.hora_inicio),
            timezone.get_current_timezone()
        )

        ventana_inicio = inicio_clase - timedelta(minutes=20)
        ventana_fin = inicio_clase + timedelta(minutes=30)

        if ventana_inicio <= ahora <= ventana_fin:
            clase_confirmable = clase
            break

    pago_form = PagoAlumnoForm()

    promociones_home = Promocion.objects.filter(
        publicada_home=True,
        activa=True,
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy,
    ).select_related('plan')
    eventos_home = Evento.objects.filter(
        publicada_home=True,
        activo=True,
    ).filter(
        Q(fecha_fin__gte=ahora)
        | Q(fecha_fin__isnull=True, fecha_inicio__gte=ahora)
    )
    publicaciones_home = sorted(
        ([{'tipo': 'PROMOCION', 'objeto': item, 'orden': item.orden}
          for item in promociones_home]
         + [{'tipo': 'EVENTO', 'objeto': item, 'orden': item.orden}
            for item in eventos_home]),
        key=lambda item: (item['orden'], 0 if item['objeto'].destacada else 1),
    )

    return render(request, 'gestion/home_publica.html', {
        'asistencias_hoy': asistencias_hoy,
        'promo_embed': promo_embed,
        'playlist_embed': playlist_embed,
        'clases_hoy': clases_hoy,
        'clase_confirmable': clase_confirmable,
        'pago_form': pago_form,
        'config_home': config_home,
        'publicaciones_home': publicaciones_home,
    })


@staff_member_required
def dashboard(request):
    alumnos = Alumno.objects.all()

    for alumno in alumnos:
        alumno.actualizar_estado()

    total_alumnos = alumnos.count()
    total_planes = Plan.objects.count()
    total_suscripciones = Suscripcion.objects.count()
    total_pagos = Pago.objects.count()
    total_instructores = Instructor.objects.filter(activo=True).count()

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

    # notificacion de estudiante nuevo

    registros_pendientes = RegistroLegalEstudiante.objects.filter(
        estado__startswith='PENDIENTE'
    ).count()

    alumnos_activos = Alumno.objects.filter(estado='ACTIVO').count()
    alumnos_proximos = Alumno.objects.filter(estado='PROXIMO_VENCER').count()
    alumnos_vencidos_total = Alumno.objects.filter(estado='VENCIDO').count()
    alumnos_suspendidos = Alumno.objects.filter(estado='SUSPENDIDO').count()

    pagos_aprobados = Pago.objects.filter(estado='APROBADO').count()
    pagos_pendientes_total = Pago.objects.filter(estado='PENDIENTE').count()
    pagos_rechazados = Pago.objects.filter(estado='RECHAZADO').count()
    pagos_programados = PagoProgramado.objects.filter(
        estado='PENDIENTE'
    ).order_by('fecha_vencimiento')[:5]

    hoy = timezone.now().date()

    movimientos_operativos = MovimientoFinanciero.objects.exclude(
        concepto__startswith='Transferencia '
    )

    ingresos_mes = movimientos_operativos.filter(
        tipo='INGRESO',
        fecha__month=hoy.month,
        fecha__year=hoy.year
    ).aggregate(total=Sum('valor'))['total'] or 0

    gastos_mes = movimientos_operativos.filter(
        tipo='EGRESO',
        fecha__month=hoy.month,
        fecha__year=hoy.year
    ).aggregate(total=Sum('valor'))['total'] or 0

    utilidad_mes = ingresos_mes - gastos_mes

    nombres_meses = (
        'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
        'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
    )
    labels_flujo = []
    ingresos_flujo = []
    gastos_flujo = []

    mes_actual_absoluto = hoy.year * 12 + hoy.month - 1
    for desplazamiento in range(5, -1, -1):
        mes_absoluto = mes_actual_absoluto - desplazamiento
        anio_flujo, indice_mes = divmod(mes_absoluto, 12)
        mes_flujo = indice_mes + 1
        labels_flujo.append(f'{nombres_meses[indice_mes]} {anio_flujo}')

        ingreso = movimientos_operativos.filter(
            tipo=MovimientoFinanciero.Tipos.INGRESO,
            fecha__year=anio_flujo,
            fecha__month=mes_flujo,
        ).aggregate(total=Sum('valor'))['total'] or 0
        gasto = movimientos_operativos.filter(
            tipo=MovimientoFinanciero.Tipos.EGRESO,
            fecha__year=anio_flujo,
            fecha__month=mes_flujo,
        ).aggregate(total=Sum('valor'))['total'] or 0

        ingresos_flujo.append(float(ingreso))
        gastos_flujo.append(float(gasto))

    cuentas_financieras = list(
        CuentaFinanciera.objects.filter(activa=True).order_by('nombre')
    )
    for cuenta in cuentas_financieras:
        cuenta.saldo_calculado = cuenta.saldo_actual

    saldo_total = sum(
        (cuenta.saldo_calculado for cuenta in cuentas_financieras),
        0,
    )
    labels_cuentas = [cuenta.nombre for cuenta in cuentas_financieras]
    saldos_cuentas = [
        float(cuenta.saldo_calculado) for cuenta in cuentas_financieras
    ]

    pagos_programados_pendientes = PagoProgramado.objects.filter(
        estado='PENDIENTE'
    ).count()

    context = {
        'total_alumnos': total_alumnos,
        'total_planes': total_planes,
        'total_suscripciones': total_suscripciones,
        'total_pagos': total_pagos,
        'pagos_pendientes': pagos_pendientes,
        'suscripciones_por_vencer': suscripciones_por_vencer,
        'alumnos_vencidos': alumnos_vencidos,
        'ultimas_notificaciones': ultimas_notificaciones,
        'total_instructores': total_instructores,
        'alumnos_activos': alumnos_activos,
        'alumnos_proximos': alumnos_proximos,
        'alumnos_vencidos_total': alumnos_vencidos_total,
        'alumnos_suspendidos': alumnos_suspendidos,
        'pagos_aprobados': pagos_aprobados,
        'pagos_pendientes_total': pagos_pendientes_total,
        'pagos_rechazados': pagos_rechazados,
        'pagos_programados': pagos_programados,
        'ingresos_mes': ingresos_mes,
        'gastos_mes': gastos_mes,
        'utilidad_mes': utilidad_mes,
        'saldo_total': saldo_total,
        'cuentas_financieras': cuentas_financieras,
        'pagos_programados_pendientes': pagos_programados_pendientes,
        'registros_pendientes': registros_pendientes,
        'hoy': hoy,
        'labels_flujo': labels_flujo,
        'ingresos_flujo': ingresos_flujo,
        'gastos_flujo': gastos_flujo,
        'labels_cuentas': labels_cuentas,
        'saldos_cuentas': saldos_cuentas,
    }
    return render(request, 'gestion/dashboard.html', context)


@staff_member_required
def lista_alumnos(request):
    alumnos = Alumno.objects.select_related('user').all()

    for alumno in alumnos:
        alumno.actualizar_estado()

    alumnos = Alumno.objects.select_related('user').all()

    return render(request, 'gestion/lista_alumnos.html', {
        'alumnos': alumnos
    })


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


# VISTA PARA CREAR PLANES

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

    return render(
        request,
        'gestion/crear_plan.html',
        {'form': form}
    )


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
        'alumno',
        'suscripcion',
        'plan',
        'promocion',
        'metodo_qr',
        'validado_por'
    ).all()
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    documento = request.GET.get('documento', '').strip()
    estado = request.GET.get('estado', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    metodo = request.GET.get('metodo', '').strip()

    if fecha_desde:
        pagos = pagos.filter(fecha_reporte__date__gte=fecha_desde)
    if fecha_hasta:
        pagos = pagos.filter(fecha_reporte__date__lte=fecha_hasta)
    if documento:
        pagos = pagos.filter(
            Q(alumno__documento__icontains=documento)
            | Q(alumno__documento_acudiente__icontains=documento)
            | Q(pagador_documento__icontains=documento)
            | Q(inscripcion_evento__participante_documento__icontains=documento)
            | Q(inscripcion_evento__acudiente_documento__icontains=documento)
        ).distinct()
    if estado:
        pagos = pagos.filter(estado=estado)
    if tipo:
        pagos = pagos.filter(tipo=tipo)
    if metodo:
        pagos = pagos.filter(metodo_qr_id=metodo)

    resumen = pagos.aggregate(
        cantidad=Count('id'),
        total=Sum('valor'),
        aprobados=Sum('valor', filter=Q(estado=Pago.Estados.APROBADO)),
        pendientes=Sum('valor', filter=Q(estado=Pago.Estados.PENDIENTE)),
        rechazados=Sum('valor', filter=Q(estado=Pago.Estados.RECHAZADO)),
    )
    return render(request, 'gestion/lista_pagos.html', {
        'pagos': pagos,
        'resumen': resumen,
        'estados_pago': Pago.Estados.choices,
        'tipos_pago': Pago.Tipos.choices,
        'metodos_pago': MetodoPagoQR.objects.all(),
        'filtros': request.GET,
    })


@staff_member_required
def crear_pago(request):
    if request.method == 'POST':
        form = PagoForm(request.POST, request.FILES)

        if form.is_valid():
            pago = form.save(commit=False)
            pago.estado = 'PENDIENTE'
            pago.suscripcion = None
            pago.tipo = Pago.Tipos.MENSUALIDAD
            if pago.alumno:
                pago.pagador_nombre = pago.alumno.nombre_acudiente or str(pago.alumno)
                pago.pagador_documento = (
                    pago.alumno.documento_acudiente or pago.alumno.documento
                )
                pago.pagador_correo = pago.alumno.user.email
            marcar_posible_duplicado(pago)
            pago.save()

            messages.success(
                request,
                'Pago registrado correctamente y quedó pendiente por validar.'
            )

            return redirect('gestion:lista_pagos')
    else:
        form = PagoForm()

    return render(request, 'gestion/crear_pago.html', {
        'form': form
    })


@staff_member_required
@transaction.atomic
def validar_pago(request, pago_id):
    pagos = Pago.objects.select_related(
        'alumno__user', 'plan', 'promocion',
        'metodo_qr__cuenta_financiera', 'duplicado_de',
    )
    if request.method == 'POST':
        pagos = pagos.select_for_update()

    pago = get_object_or_404(pagos, id=pago_id)

    if pago.estado != 'PENDIENTE':
        messages.warning(request, 'Este pago ya fue validado.')
        return redirect('gestion:lista_pagos')

    if request.method == 'POST':
        form = ValidarPagoForm(request.POST, instance=pago)

        if form.is_valid():
            pago = form.save(commit=False)
            pago.validado_por = request.user
            pago.fecha_validacion = timezone.now()
            pago.justificacion_duplicado = form.cleaned_data.get(
                'justificacion_duplicado', ''
            )

            if pago.estado == 'APROBADO':
                hoy = timezone.now().date()
                if pago.tipo in (Pago.Tipos.MENSUALIDAD, Pago.Tipos.PROMOCION):
                    if not pago.alumno_id or not pago.plan_id:
                        messages.error(
                            request,
                            'El pago necesita estudiante y plan para crear la suscripción.',
                        )
                        return redirect('gestion:validar_pago', pago_id=pago.id)
                    fecha_inicio = form.cleaned_data['fecha_inicio']
                    fecha_vencimiento = form.fecha_vencimiento_calculada()
                    estado_suscripcion = (
                        Suscripcion.Estados.ACTIVA
                        if fecha_inicio <= hoy <= fecha_vencimiento
                        else Suscripcion.Estados.PROGRAMADA
                    )
                    if estado_suscripcion == Suscripcion.Estados.ACTIVA:
                        Suscripcion.objects.filter(
                            alumno=pago.alumno,
                            estado=Suscripcion.Estados.ACTIVA,
                            fecha_vencimiento__gte=fecha_inicio,
                        ).update(estado=Suscripcion.Estados.FINALIZADA)
                    beneficio = ''
                    if pago.promocion_id:
                        beneficio = (
                            f'Promoción: {pago.promocion.nombre}. '
                            f'{pago.promocion.condiciones}'
                        ).strip()
                    suscripcion = Suscripcion.objects.create(
                        alumno=pago.alumno,
                        plan=pago.plan,
                        fecha_inicio=fecha_inicio,
                        fecha_vencimiento=fecha_vencimiento,
                        estado=estado_suscripcion,
                        precio_aplicado=pago.valor,
                        detalle_beneficio=beneficio,
                    )
                    pago.suscripcion = suscripcion
                    pago.concepto_detalle = (
                        f'{pago.plan.nombre}'
                        + (f' - {pago.promocion.nombre}' if pago.promocion_id else '')
                    )
                    if estado_suscripcion == Suscripcion.Estados.ACTIVA:
                        pago.alumno.estado = Alumno.Estados.ACTIVO
                        pago.alumno.save(update_fields=['estado'])
                    if hasattr(pago, 'aplicacion_promocion'):
                        pago.aplicacion_promocion.estado = AplicacionPromocion.Estados.APLICADA
                        pago.aplicacion_promocion.save(update_fields=['estado'])
                elif pago.tipo == Pago.Tipos.EVENTO:
                    inscripcion = getattr(pago, 'inscripcion_evento', None)
                    if not inscripcion:
                        messages.error(request, 'El pago no tiene una inscripción asociada.')
                        return redirect('gestion:validar_pago', pago_id=pago.id)
                    if inscripcion.evento.cupos_disponibles == 0:
                        messages.error(request, 'El evento ya no tiene cupos disponibles.')
                        return redirect('gestion:validar_pago', pago_id=pago.id)
                    inscripcion.estado = InscripcionEvento.Estados.CONFIRMADA
                    inscripcion.save(update_fields=['estado'])
                    pago.concepto_detalle = (
                        f'{inscripcion.evento.get_tipo_display()}: '
                        f'{inscripcion.evento.nombre}'
                    )

                if not pago.numero_comprobante:
                    pago.numero_comprobante = f'CP-{hoy.year}-{pago.id:06d}'
                pago.fecha_comprobante = timezone.now()
                pago.save()

                cuenta = pago.metodo_qr.cuenta_financiera
                categoria_nombre = {
                    Pago.Tipos.MENSUALIDAD: 'Mensualidades',
                    Pago.Tipos.PROMOCION: 'Promociones academia',
                    Pago.Tipos.EVENTO: 'Eventos academia',
                }.get(pago.tipo, 'Otros ingresos academia')
                categoria = CategoriaFinanciera.objects.filter(
                    nombre=categoria_nombre
                ).first()

                if cuenta:
                    MovimientoFinanciero.objects.get_or_create(
                        pago=pago,
                        defaults={
                            'cuenta': cuenta,
                            'tipo': 'INGRESO',
                            'concepto': pago.concepto_detalle or f'Pago #{pago.id}',
                            'valor': pago.valor,
                            'fecha': pago.fecha_validacion,
                            'observaciones': f'Ingreso generado automáticamente desde el pago #{pago.id}.',
                            'categoria': categoria,
                        }
                    )
                else:
                    messages.warning(
                        request,
                        'Pago aprobado, pero no se creó movimiento financiero porque el método de pago no tiene cuenta asociada.'
                    )

                messages.success(
                    request,
                    'Pago aprobado y comprobante generado correctamente.'
                )
                try:
                    enviar_comprobante_pago(pago)
                    messages.info(request, 'El comprobante fue enviado por correo.')
                except ValueError:
                    messages.info(
                        request,
                        'El comprobante está disponible para descarga; no hay correo asociado.',
                    )
                except Exception as error:
                    pago.error_envio_comprobante = str(error)[:500]
                    pago.save(update_fields=['error_envio_comprobante'])
                    messages.warning(
                        request,
                        'El pago fue aprobado, pero el correo no pudo enviarse. Puedes reenviarlo.',
                    )

            elif pago.estado == 'RECHAZADO':
                pago.save()

                if hasattr(pago, 'aplicacion_promocion'):
                    pago.aplicacion_promocion.estado = AplicacionPromocion.Estados.RECHAZADA
                    pago.aplicacion_promocion.save(update_fields=['estado'])
                if hasattr(pago, 'inscripcion_evento'):
                    pago.inscripcion_evento.estado = InscripcionEvento.Estados.RECHAZADA
                    pago.inscripcion_evento.save(update_fields=['estado'])

                messages.warning(
                    request,
                    'Pago rechazado correctamente.'
                )

            return redirect('gestion:lista_pagos')

    else:
        form = ValidarPagoForm(instance=pago)

    return render(request, 'gestion/validar_pago.html', {
        'form': form,
        'pago': pago,
        'ultima_suscripcion': (
            Suscripcion.objects.filter(alumno=pago.alumno)
            .order_by('-fecha_vencimiento').first()
            if pago.alumno_id else None
        ),
        'dias_cobertura': (
            pago.promocion.dias_aplicados if pago.promocion_id
            else pago.plan.duracion_dias if pago.plan_id else None
        ),
    })


@staff_member_required
def editar_alumno(request, alumno_id):

    alumno = get_object_or_404(
        Alumno,
        id=alumno_id
    )

    usuario = alumno.user

    if request.method == 'POST':

        usuario_form = UsuarioAlumnoEditForm(
            request.POST,
            instance=usuario
        )

        alumno_form = AlumnoForm(
            request.POST,
            instance=alumno
        )

        if usuario_form.is_valid() and alumno_form.is_valid():

            usuario_form.save()
            alumno_form.save()

            messages.success(
                request,
                'Alumno actualizado correctamente.'
            )

            return redirect('gestion:lista_alumnos')

    else:

        usuario_form = UsuarioAlumnoEditForm(
            instance=usuario
        )

        alumno_form = AlumnoForm(
            instance=alumno
        )

    return render(
        request,
        'gestion/editar_alumno.html',
        {
            'usuario_form': usuario_form,
            'alumno_form': alumno_form,
            'alumno': alumno,
        }
    )


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

    return render(request, 'gestion/editar_suscripcion.html', {
        'form': form,
        'suscripcion': suscripcion,
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


# VISTA PARA ASISTENCIA A CLASE

@login_required
def mi_asistencia(request):
    alumno = get_object_or_404(Alumno, user=request.user)
    hoy = timezone.localdate()

    try:
        anio = int(request.GET.get('anio', hoy.year))
        mes = int(request.GET.get('mes', hoy.month))
        if not 1 <= mes <= 12 or not 2000 <= anio <= 2100:
            raise ValueError
    except (TypeError, ValueError):
        anio, mes = hoy.year, hoy.month

    primer_dia = datetime(anio, mes, 1).date()
    if mes == 12:
        siguiente_mes = datetime(anio + 1, 1, 1).date()
    else:
        siguiente_mes = datetime(anio, mes + 1, 1).date()

    asistencias = AsistenciaClase.objects.filter(
        alumno=alumno,
        estado=AsistenciaClase.Estados.CONFIRMADA,
        fecha_clase__gte=primer_dia,
        fecha_clase__lt=siguiente_mes,
    ).select_related('clase').order_by('fecha_clase', 'clase__hora_inicio')

    asistencias_por_dia = {}
    for asistencia in asistencias:
        asistencias_por_dia.setdefault(asistencia.fecha_clase.day, []).append(
            asistencia
        )

    suscripciones = list(Suscripcion.objects.filter(
        alumno=alumno,
        fecha_inicio__lt=siguiente_mes,
        fecha_vencimiento__gte=primer_dia,
    ).select_related('plan').order_by('fecha_inicio'))
    inicios_mensualidad = {
        suscripcion.fecha_inicio for suscripcion in suscripciones
        if primer_dia <= suscripcion.fecha_inicio < siguiente_mes
    }
    finales_mensualidad = {
        suscripcion.fecha_vencimiento for suscripcion in suscripciones
        if primer_dia <= suscripcion.fecha_vencimiento < siguiente_mes
    }

    calendario = calendar.Calendar(firstweekday=0)
    semanas = []
    for semana in calendario.monthdatescalendar(anio, mes):
        dias_semana = []
        for fecha in semana:
            del_mes = fecha.month == mes
            asistencias_dia = (
                asistencias_por_dia.get(fecha.day, []) if del_mes else []
            )
            dias_semana.append({
                'fecha': fecha,
                'del_mes': del_mes,
                'es_hoy': fecha == hoy,
                'asistencias': asistencias_dia,
                'inicio_mensualidad': fecha in inicios_mensualidad,
                'fin_mensualidad': fecha in finales_mensualidad,
            })
        semanas.append(dias_semana)

    anterior = (primer_dia - timedelta(days=1))
    siguiente = siguiente_mes
    nombres_meses = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]

    return render(request, 'gestion/mi_asistencia.html', {
        'alumno': alumno,
        'semanas': semanas,
        'nombre_mes': nombres_meses[mes],
        'mes': mes,
        'anio': anio,
        'anterior': anterior,
        'siguiente': siguiente,
        'total_asistencias': asistencias.count(),
        'dias_asistidos': len(asistencias_por_dia),
    })


# @login_required
def horario_clases(request):

    if request.user.is_authenticated:

        if request.user.debe_cambiar_password:

            return redirect(
                'gestion:cambio_password_obligatorio'
            )

    modo_cortesia = request.GET.get('cortesia', '').upper()
    tipos_cortesia = {
        ClaseProgramada.PublicosObjetivo.ADULTO,
        ClaseProgramada.PublicosObjetivo.MENOR,
    }
    if modo_cortesia not in tipos_cortesia:
        modo_cortesia = None

    if not request.user.is_authenticated and not modo_cortesia:
        return redirect('gestion:home_publica')

    hoy = timezone.now().date()

    clases = ClaseProgramada.objects.filter(
        activa=True
    ).select_related(
        'instructor__user'
    ).annotate(
        total_asistentes=Count(
            'asistencias',
            filter=Q(
                asistencias__fecha_clase=hoy,
                asistencias__estado='CONFIRMADA'
            )
        )
    )

    if modo_cortesia:
        clases = clases.filter(publico_objetivo__in=[
            ClaseProgramada.PublicosObjetivo.TODOS,
            modo_cortesia,
        ])

    orden_dias = {
        'LUNES': 1,
        'MARTES': 2,
        'MIERCOLES': 3,
        'JUEVES': 4,
        'VIERNES': 5,
        'SABADO': 6,
        'DOMINGO': 7,
    }

    dias = sorted(
        set(
            clases.values_list(
                'dia',
                flat=True
            )
        ),
        key=lambda dia: orden_dias.get(dia, 99)
    )

    horas = list(
        clases.values_list('hora_inicio', flat=True)
        .distinct()
        .order_by('hora_inicio')
    )

    horario = []

    for hora in horas:
        fila = {
            'hora': hora,
            'dias': []
        }

        for dia in dias:
            clase = clases.filter(dia=dia, hora_inicio=hora).first()
            fila['dias'].append({
                'dia': dia,
                'clase': clase
            })

        horario.append(fila)

    ahora = timezone.localtime()

    metodos_pago = MetodoPagoQR.objects.filter(activo=True)

    pago_form = PagoAlumnoForm()

    return render(request, 'gestion/horario_clases.html', {
        'dias': dias,
        'horario': horario,
        'hora_actual': ahora,
        'metodos_pago': metodos_pago,
        'pago_form': pago_form,
        'modo_cortesia': modo_cortesia,
    })


@login_required
def confirmar_asistencia(request, clase_id):
    clase = get_object_or_404(ClaseProgramada, id=clase_id, activa=True)

    if not hasattr(request.user, 'perfil_alumno'):
        messages.error(
            request, 'Solo los alumnos pueden confirmar asistencia.')
        return redirect('gestion:horario_clases')

    alumno = request.user.perfil_alumno
    ahora = timezone.localtime()
    hoy = ahora.date()

    inicio_clase = datetime.combine(hoy, clase.hora_inicio)
    inicio_clase = timezone.make_aware(inicio_clase)

    ventana_inicio = inicio_clase - timedelta(minutes=20)
    ventana_fin = inicio_clase + timedelta(minutes=10)

    if not (ventana_inicio <= ahora <= ventana_fin):
        messages.warning(
            request,
            'La asistencia solo puede confirmarse desde 20 minutos antes hasta 10 minutos después de iniciar la clase.'
        )
        return redirect('gestion:horario_clases')

    # CUPO LLENO
    total_asistentes = AsistenciaClase.objects.filter(
        clase=clase,
        fecha_clase=hoy,
        estado='CONFIRMADA'
    ).count()

    ya_confirmo = AsistenciaClase.objects.filter(
        alumno=alumno,
        clase=clase,
        fecha_clase=hoy,
        estado='CONFIRMADA'
    ).exists()

    if not ya_confirmo and total_asistentes >= clase.cupo_maximo:
        messages.error(request, 'No hay cupos disponibles para esta clase.')
        logout(request)
        return redirect('gestion:horario_clases')

    asistencia, creada = AsistenciaClase.objects.get_or_create(
        alumno=alumno,
        clase=clase,
        fecha_clase=hoy,
        defaults={
            'estado': 'CONFIRMADA',
            'fecha_confirmacion': ahora,
        }
    )

    if not creada:
        messages.info(
            request, 'Ya habías confirmado asistencia para esta clase.'
        )
    else:
        messages.success(request, 'Asistencia confirmada correctamente.')

    logout(request)
    return redirect('gestion:horario_clases')


# EDICION DE HORARIOS

@staff_member_required
def crear_clase(request):
    if request.method == 'POST':
        form = ClaseProgramadaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Clase creada correctamente.')
            return redirect('gestion:horario_clases')
    else:
        form = ClaseProgramadaForm()

    return render(request, 'gestion/formulario.html', {
        'form': form,
        'titulo': 'Crear clase',
        'cancelar_url': 'gestion:horario_clases'
    })


@staff_member_required
def editar_clase(request, clase_id):
    clase = get_object_or_404(ClaseProgramada, id=clase_id)

    if request.method == 'POST':
        form = ClaseProgramadaForm(request.POST, instance=clase)
        if form.is_valid():
            form.save()
            messages.success(request, 'Clase actualizada correctamente.')
            return redirect('gestion:configurar_horario')
    else:
        form = ClaseProgramadaForm(instance=clase)

    return render(request, 'gestion/formulario.html', {
        'form': form,
        'titulo': 'Editar clase',
        'cancelar_url': 'gestion:configurar_horario'
    })


@staff_member_required
@require_POST
def eliminar_clase(request, clase_id):

    clase = get_object_or_404(
        ClaseProgramada,
        id=clase_id
    )

    clase.delete()

    messages.success(
        request,
        'Clase eliminada correctamente.'
    )

    return redirect('gestion:configurar_horario')

# VERIFICAR ASISTENCIA EN KIOSKO


@require_POST
def confirmar_asistencia_kiosko(request):
    clase_id = request.POST.get('clase_id')
    username = request.POST.get('username')
    password = request.POST.get('password')

    clase = get_object_or_404(ClaseProgramada, id=clase_id, activa=True)

    user = authenticate(request, username=username, password=password)

    if user is None:
        messages.error(request, 'Usuario o contraseña incorrectos.')
        return redirect('gestion:horario_clases')

    if not hasattr(user, 'perfil_alumno'):
        messages.error(request, 'Este usuario no está registrado como alumno.')
        return redirect('gestion:horario_clases')

    alumno = user.perfil_alumno
    ahora = timezone.localtime()
    hoy = ahora.date()

    inicio_clase = datetime.combine(hoy, clase.hora_inicio)
    inicio_clase = timezone.make_aware(inicio_clase)

    ventana_inicio = inicio_clase - timedelta(minutes=20)
    ventana_fin = inicio_clase + timedelta(minutes=10)

    if not (ventana_inicio <= ahora <= ventana_fin):
        messages.warning(
            request,
            'La asistencia solo puede confirmarse desde 20 minutos antes hasta 10 minutos después de iniciar la clase.'
        )
        return redirect('gestion:horario_clases')

    total_asistentes = AsistenciaClase.objects.filter(
        clase=clase,
        fecha_clase=hoy,
        estado='CONFIRMADA'
    ).count()

    ya_confirmo = AsistenciaClase.objects.filter(
        alumno=alumno,
        clase=clase,
        fecha_clase=hoy,
        estado='CONFIRMADA'
    ).exists()

    if not ya_confirmo and total_asistentes >= clase.cupo_maximo:
        messages.error(request, 'No hay cupos disponibles para esta clase.')
        return redirect('gestion:horario_clases')

    asistencia, creada = AsistenciaClase.objects.get_or_create(
        alumno=alumno,
        clase=clase,
        fecha_clase=hoy,
        defaults={
            'estado': 'CONFIRMADA',
            'fecha_confirmacion': ahora,
        }
    )

    if creada:
        messages.success(request, 'Asistencia confirmada correctamente.')
    else:
        messages.info(
            request, 'Ya habías confirmado asistencia para esta clase.')

    return redirect('gestion:horario_clases')


# ESTUDIANTES EN CLASE

@staff_member_required
def asistentes_clase(request, clase_id):
    clase = get_object_or_404(ClaseProgramada, id=clase_id)

    hoy = timezone.now().date()

    asistencias = AsistenciaClase.objects.filter(
        clase=clase,
        fecha_clase=hoy,
        estado='CONFIRMADA'
    ).select_related('alumno__user')

    return render(request, 'gestion/asistentes_clase.html', {
        'clase': clase,
        'asistencias': asistencias,
        'total_asistentes': asistencias.count(),
        'hoy': hoy,
    })


def registrar_pago_alumno(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, 'Usuario o contraseña incorrectos.')
            return redirect('gestion:home_publica')

        if not hasattr(user, 'perfil_alumno'):
            messages.error(
                request,
                'Este usuario no está registrado como alumno.'
            )
            return redirect('gestion:home_publica')

        alumno = user.perfil_alumno

        form = PagoAlumnoForm(request.POST, request.FILES)

        if form.is_valid():
            pago = form.save(commit=False)

            pago.alumno = alumno
            pago.suscripcion = None
            pago.estado = 'PENDIENTE'
            pago.tipo = Pago.Tipos.MENSUALIDAD
            pago.pagador_nombre = alumno.nombre_acudiente or str(alumno)
            pago.pagador_documento = (
                alumno.documento_acudiente or alumno.documento
            )
            pago.pagador_correo = alumno.user.email

            marcar_posible_duplicado(pago)
            pago.save()

            if pago.posible_duplicado:
                messages.warning(
                    request,
                    'Pago recibido y marcado para revisión porque coincide con otro registro.',
                )
            else:
                messages.success(
                    request,
                    'Pago registrado correctamente. Queda pendiente de validación.'
                )

            return redirect('gestion:home_publica')

        messages.error(request, 'Revisa los datos del pago.')
        return redirect('gestion:home_publica')

    return redirect('gestion:home_publica')

# RESTABLECER CONTRASEÑA


@staff_member_required
def reset_password_alumno(request, alumno_id):

    alumno = get_object_or_404(Alumno, id=alumno_id)

    nueva_clave = str(random.randint(100000, 999999))

    alumno.user.password = make_password(nueva_clave)

    alumno.user.save()

    messages.success(
        request,
        f'Nueva contraseña temporal: {nueva_clave}'
    )

    return redirect('gestion:editar_alumno', alumno_id=alumno.id)

# REGISTRO DE GASTOS


@staff_member_required
def registrar_gasto(request):
    if request.method == 'POST':
        form = GastoForm(request.POST)

        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.tipo = 'EGRESO'
            gasto.save()

            messages.success(request, 'Gasto registrado correctamente.')
            return redirect('gestion:dashboard')

    else:
        form = GastoForm()

    cuentas = CuentaFinanciera.objects.filter(activa=True)

    return render(request, 'gestion/registrar_gasto.html', {
        'form': form,
        'cuentas': cuentas,
    })


# VISTA DE PAGOS PROGRAMADOS

@staff_member_required
def crear_pago_programado(request):
    if request.method == 'POST':
        form = PagoProgramadoForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Pago programado creado correctamente.')
            return redirect('gestion:dashboard')
    else:
        form = PagoProgramadoForm()

    return render(request, 'gestion/crear_pago_programado.html', {
        'form': form,
    })


# VISTA DE PAGOS PROGRAMADOS

@staff_member_required
@require_POST
def pagar_pago_programado(request, pago_id):
    with transaction.atomic():
        pago_programado = get_object_or_404(
            PagoProgramado.objects.select_for_update(),
            id=pago_id
        )

        if pago_programado.estado != PagoProgramado.Estados.PENDIENTE:
            messages.warning(
                request,
                'Solo se pueden pagar obligaciones que estén pendientes.'
            )
            return redirect('gestion:dashboard')

        if not pago_programado.cuenta_pago:
            messages.error(
                request,
                'El pago programado no tiene cuenta asignada.'
            )
            return redirect('gestion:dashboard')

        MovimientoFinanciero.objects.create(
            cuenta=pago_programado.cuenta_pago,
            tipo=MovimientoFinanciero.Tipos.EGRESO,
            concepto=f'Pago programado - {pago_programado.concepto}',
            valor=pago_programado.valor,
            fecha=timezone.now(),
            observaciones='Generado automáticamente desde pago programado.'
        )

        pago_programado.estado = PagoProgramado.Estados.PAGADO
        pago_programado.fecha_pago = timezone.now()
        pago_programado.save(update_fields=['estado', 'fecha_pago'])

    messages.success(request, 'Pago registrado correctamente.')

    return redirect('gestion:dashboard')

# VISTA DETALLADA DE LOS GASTOS E INGRESOS


@staff_member_required
def detalle_financiero(request):

    hoy = timezone.now().date()

    try:
        mes = int(request.GET.get('mes', hoy.month))
    except (TypeError, ValueError):
        mes = hoy.month

    try:
        anio = int(request.GET.get('anio', hoy.year))
    except (TypeError, ValueError):
        anio = hoy.year

    if not 1 <= mes <= 12:
        mes = hoy.month
    if not 2000 <= anio <= 2100:
        anio = hoy.year

    tipo = request.GET.get('tipo', '')

    movimientos = MovimientoFinanciero.objects.filter(
        fecha__month=mes,
        fecha__year=anio
    ).select_related('cuenta', 'pago')

    if tipo in ['INGRESO', 'EGRESO']:
        movimientos = movimientos.filter(tipo=tipo)

    movimientos_operativos = movimientos.exclude(
        concepto__startswith='Transferencia '
    )

    total_ingresos = movimientos_operativos.filter(
        tipo='INGRESO'
    ).aggregate(
        total=Sum('valor')
    )['total'] or 0

    total_egresos = movimientos_operativos.filter(
        tipo='EGRESO'
    ).aggregate(
        total=Sum('valor')
    )['total'] or 0

    saldo_mes = total_ingresos - total_egresos

    ingresos_por_mes = []
    egresos_por_mes = []

    for m in range(1, 13):

        ingresos = MovimientoFinanciero.objects.exclude(
            concepto__startswith='Transferencia '
        ).filter(
            tipo='INGRESO',
            fecha__year=anio,
            fecha__month=m
        ).aggregate(
            total=Sum('valor')
        )['total'] or 0

        egresos = MovimientoFinanciero.objects.exclude(
            concepto__startswith='Transferencia '
        ).filter(
            tipo='EGRESO',
            fecha__year=anio,
            fecha__month=m
        ).aggregate(
            total=Sum('valor')
        )['total'] or 0

        ingresos_por_mes.append(float(ingresos))
        egresos_por_mes.append(float(egresos))

    gastos_por_categoria = MovimientoFinanciero.objects.filter(
        tipo='EGRESO',
        fecha__year=anio,
        fecha__month=mes,
        categoria__isnull=False
    ).values(
        'categoria__nombre'
    ).annotate(
        total=Sum('valor')
    ).order_by('-total')

    labels_gastos_categoria = [
        item['categoria__nombre']
        for item in gastos_por_categoria
    ]

    datos_gastos_categoria = [
        float(item['total'])
        for item in gastos_por_categoria
    ]

    return render(request, 'gestion/detalle_financiero.html', {

        'movimientos': movimientos,

        'mes': mes,
        'anio': anio,
        'tipo': tipo,

        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos,
        'saldo_mes': saldo_mes,

        'ingresos_por_mes': ingresos_por_mes,
        'egresos_por_mes': egresos_por_mes,

        'gastos_por_categoria': gastos_por_categoria,
        'labels_gastos_categoria': labels_gastos_categoria,
        'datos_gastos_categoria': datos_gastos_categoria,

    })
# TRANSFERENCIAS ENTRE CUENTAS


@staff_member_required
def registrar_transferencia(request):
    if request.method == 'POST':
        form = TransferenciaForm(request.POST)

        if form.is_valid():
            origen = form.cleaned_data['cuenta_origen']
            destino = form.cleaned_data['cuenta_destino']
            valor = form.cleaned_data['valor']
            concepto = form.cleaned_data['concepto']
            observaciones = form.cleaned_data['observaciones']

            with transaction.atomic():
                MovimientoFinanciero.objects.create(
                    cuenta=origen,
                    tipo='EGRESO',
                    concepto=f'Transferencia salida - {concepto}',
                    valor=valor,
                    observaciones=f'Destino: {destino}. {observaciones}'
                )

                MovimientoFinanciero.objects.create(
                    cuenta=destino,
                    tipo='INGRESO',
                    concepto=f'Transferencia entrada - {concepto}',
                    valor=valor,
                    observaciones=f'Origen: {origen}. {observaciones}'
                )

            messages.success(
                request, 'Transferencia registrada correctamente.')
            return redirect('gestion:dashboard')

    else:
        form = TransferenciaForm()

    return render(request, 'gestion/registrar_transferencia.html', {
        'form': form,
    })

# VISTA DE REGISTROS LEGALES


@staff_member_required
def lista_registros_legales(request):
    registros = RegistroLegalEstudiante.objects.all()

    return render(request, 'gestion/lista_registros_legales.html', {
        'registros': registros
    })

# DETALLE DE REGISTRO LEGAL


@staff_member_required
def detalle_registro_legal(request, registro_id):

    registro = get_object_or_404(
        RegistroLegalEstudiante,
        id=registro_id
    )

    return render(
        request,
        'gestion/detalle_registro_legal.html',
        {
            'registro': registro
        }
    )

# VISTAS PARA REGISTROS LEGALES


@staff_member_required
@require_POST
def aprobar_registro_legal(request, registro_id):

    registro = get_object_or_404(
        RegistroLegalEstudiante,
        id=registro_id
    )

    if registro.estado == 'APROBADO':
        messages.warning(
            request,
            'Este registro ya fue aprobado.'
        )

        return redirect(
            'gestion:detalle_registro_legal',
            registro_id=registro.id
        )

    alumno, _, error = crear_alumno_desde_registro(
        registro
    )

    if error:

        messages.error(
            request,
            error
        )

        return redirect(
            'gestion:detalle_registro_legal',
            registro_id=registro.id
        )

    registro.estado = 'APROBADO'
    registro.save()

    enviar_correo_bienvenida_alumno(registro)

    messages.success(
        request,
        f'Alumno creado correctamente. Usuario: {registro.usuario_solicitado}'
    )

    return redirect(
        'gestion:detalle_registro_legal',
        registro_id=registro.id
    )


@staff_member_required
def rechazar_registro_legal(request, registro_id):
    registro = get_object_or_404(RegistroLegalEstudiante, id=registro_id)

    if request.method == 'POST':
        observacion = request.POST.get('observacion_admin', '')

        registro.estado = 'RECHAZADO'
        registro.observacion_admin = observacion
        registro.save()

        messages.warning(request, 'Registro legal rechazado.')

        return redirect('gestion:detalle_registro_legal', registro_id=registro.id)

    return render(request, 'gestion/rechazar_registro_legal.html', {
        'registro': registro,
    })


# VISTA DE CAMBIO DE CLAVE OBLIGATORIO

@login_required
def cambio_password_obligatorio(request):
    if not request.user.debe_cambiar_password:
        return redirect('gestion:horario_clases')

    if request.method == 'POST':
        form = CambioPasswordObligatorioForm(
            user=request.user,
            data=request.POST
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.debe_cambiar_password = False
                    user.save()
            except IntegrityError:
                form.add_error(
                    'username',
                    'Este nombre de usuario ya está en uso. Elige otro.'
                )
            else:
                update_session_auth_hash(request, user)
                messages.success(
                    request,
                    'Contraseña y datos de acceso actualizados correctamente.'
                )
                return redirect('gestion:horario_clases')
    else:
        form = CambioPasswordObligatorioForm(user=request.user)

    return render(request, 'gestion/cambio_password_obligatorio.html', {
        'form': form,
    })


@login_required
def cambiar_usuario(request):
    if request.user.username_modificado:
        messages.info(
            request,
            'Ya utilizaste el cambio único de nombre de usuario.'
        )
        return redirect('gestion:horario_clases')

    if request.method == 'POST':
        form = CambiarUsuarioForm(request.user, data=request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
            except IntegrityError:
                form.add_error(
                    'username',
                    'Este nombre de usuario ya está en uso. Elige otro.'
                )
            else:
                update_session_auth_hash(request, user)
                messages.success(
                    request,
                    'Nombre de usuario actualizado. Este fue tu único cambio disponible.'
                )
                return redirect('gestion:horario_clases')
    else:
        form = CambiarUsuarioForm(
            request.user,
            initial={'username': request.user.username},
        )

    return render(request, 'gestion/cambiar_usuario.html', {'form': form})

# VISTA PARA DESCARGAR PDF


@staff_member_required
def descargar_pdf_registro_legal(request, registro_id):
    registro = get_object_or_404(RegistroLegalEstudiante, id=registro_id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="registro_legal_{registro.documento}.pdf"'
    )

    p = canvas.Canvas(response)
    width, height = p._pagesize

    y = 800

    p.setFont("Helvetica-Bold", 16)
    p.drawString(60, y, "REGISTRO LEGAL DE ESTUDIANTE")
    y -= 35

    p.setFont("Helvetica", 10)
    p.drawString(60, y, f"Nombre: {registro.nombres} {registro.apellidos}")
    y -= 18
    p.drawString(60, y, f"Documento: {registro.documento}")
    y -= 18
    p.drawString(60, y, f"Tipo: {registro.get_tipo_estudiante_display()}")
    y -= 18
    p.drawString(60, y, f"Fecha nacimiento: {registro.fecha_nacimiento}")
    y -= 18
    p.drawString(60, y, f"Dirección: {registro.direccion}")
    y -= 18
    p.drawString(60, y, f"Celular: {registro.celular}")
    y -= 18
    p.drawString(60, y, f"Correo: {registro.correo or 'No registrado'}")
    y -= 18
    p.drawString(60, y, f"EPS: {registro.eps}")
    y -= 25

    p.setFont("Helvetica-Bold", 12)
    p.drawString(60, y, "Condición médica")
    y -= 18

    p.setFont("Helvetica", 10)
    p.drawString(60, y, registro.condicion_medica[:100])
    y -= 30

    if registro.tipo_estudiante == 'MENOR':
        p.setFont("Helvetica-Bold", 12)
        p.drawString(60, y, "Datos del acudiente")
        y -= 18

        p.setFont("Helvetica", 10)
        p.drawString(60, y, f"Nombre: {registro.nombre_acudiente}")
        y -= 18
        p.drawString(60, y, f"Documento: {registro.documento_acudiente}")
        y -= 18
        p.drawString(60, y, f"Parentesco: {registro.parentesco_acudiente}")
        y -= 18
        p.drawString(60, y, f"Celular: {registro.celular_acudiente}")
        y -= 30
    acuerdos = [
        {
            'titulo': 'Reglamento interno',
            'texto': (
                'Declaro que conozco y acepto el reglamento interno de la academia, '
                'sus normas de conducta, disciplina, respeto, puntualidad, cuidado de las '
                'instalaciones y comportamiento durante entrenamientos, clases o eventos.'
            ),
            'aceptado': registro.acepta_reglamento,
            'etiqueta': 'Reglamento aceptado'
        },
        {
            'titulo': 'Responsabilidad medica y riesgos deportivos',
            'texto': (
                'Declaro que he sido informado sobre las caracteristicas de la actividad '
                'deportiva y entiendo que la practica de artes marciales puede implicar '
                'riesgos como golpes, caidas, lesiones musculares, articulares, accidentes '
                'o afectaciones de salud. Participo voluntariamente y asumo dichos riesgos.'
            ),
            'aceptado': registro.acepta_riesgos,
            'etiqueta': 'Riesgos deportivos aceptados'
        },
        {
            'titulo': 'Autorizacion de uso de imagen y datos personales',
            'texto': (
                'Autorizo de manera gratuita el uso de imagenes individuales o grupales '
                'tomadas durante entrenamientos, clases, eventos deportivos o actividades '
                'realizadas por la academia. Entiendo que esta autorizacion es opcional.'
            ),
            'aceptado': registro.autoriza_imagen,
            'etiqueta': 'Autoriza uso de imagen'
        },
    ]

    for acuerdo in acuerdos:
        if y < 180:
            p.showPage()
            y = 800

        p.setFont("Helvetica-Bold", 12)
        p.drawString(60, y, acuerdo['titulo'])
        y -= 18

        p.setFont("Helvetica", 9)

        texto = acuerdo['texto']
        lineas = []
        while len(texto) > 95:
            corte = texto[:95].rfind(' ')
            lineas.append(texto[:corte])
            texto = texto[corte:].strip()
        lineas.append(texto)

        for linea in lineas:
            p.drawString(60, y, linea)
            y -= 14

        y -= 6
        p.setFont("Helvetica-Bold", 10)
        p.drawString(
            60,
            y,
            f"{acuerdo['etiqueta']}: {'SI' if acuerdo['aceptado'] else 'NO'}"
        )
        y -= 28

    p.setFont("Helvetica", 10)
    p.drawString(
        60, y, f"Reglamento aceptado: {'Sí' if registro.acepta_reglamento else 'No'}")
    y -= 18
    p.drawString(
        60, y, f"Riesgos deportivos aceptados: {'Sí' if registro.acepta_riesgos else 'No'}")
    y -= 18
    p.drawString(
        60, y, f"Autoriza uso de imagen: {'Sí' if registro.autoriza_imagen else 'No'}")
    y -= 30

    p.setFont("Helvetica-Bold", 12)
    p.drawString(60, y, "Firma")
    y -= 18

    p.setFont("Helvetica", 10)
    p.drawString(60, y, f"Fecha firma: {registro.fecha_firma}")
    y -= 18
    p.drawString(60, y, f"IP firma: {registro.ip_firma or 'No registrada'}")

    y -= 40

    p.setFont("Helvetica-Bold", 12)
    p.drawString(60, y, "Firma digital")
    y -= 20

    if registro.firma_base64:
        try:
            firma_data = registro.firma_base64.split(',')[1]
            firma_bytes = base64.b64decode(firma_data)
            firma_imagen = ImageReader(BytesIO(firma_bytes))

            p.drawImage(
                firma_imagen,
                60,
                y - 100,
                width=250,
                height=90,
                preserveAspectRatio=True,
                mask='auto'
            )

            y -= 120

        except Exception:
            p.setFont("Helvetica", 10)
            p.drawString(60, y, "No fue posible cargar la firma digital.")
        else:
            p.setFont("Helvetica", 10)
            p.drawString(60, y, "No hay firma registrada.")

    p.showPage()
    p.save()

    return response


# PROMOCIONES, EVENTOS Y COMPROBANTES


@staff_member_required
def promociones_eventos(request):
    return render(request, 'gestion/promociones_eventos.html', {
        'promociones': Promocion.objects.select_related('plan').all(),
        'eventos': Evento.objects.prefetch_related('categorias').all(),
    })


@staff_member_required
def editar_promocion(request, promocion_id=None):
    promocion = get_object_or_404(Promocion, id=promocion_id) if promocion_id else None
    form = PromocionForm(request.POST or None, request.FILES or None, instance=promocion)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Promoción guardada correctamente.')
        return redirect('gestion:promociones_eventos')
    return render(request, 'gestion/publicacion_formulario.html', {
        'form': form,
        'titulo': 'Editar promoción' if promocion else 'Nueva promoción',
        'icono': 'fa-tags',
    })


@staff_member_required
def editar_evento(request, evento_id=None):
    evento = get_object_or_404(Evento, id=evento_id) if evento_id else None
    form = EventoForm(request.POST or None, request.FILES or None, instance=evento)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Evento guardado correctamente.')
        return redirect('gestion:promociones_eventos')
    return render(request, 'gestion/publicacion_formulario.html', {
        'form': form,
        'titulo': 'Editar evento' if evento else 'Nuevo seminario, torneo o evento',
        'icono': 'fa-calendar-star',
    })


@staff_member_required
def editar_categoria_evento(request, evento_id, categoria_id=None):
    evento = get_object_or_404(Evento, id=evento_id)
    if evento.tipo != Evento.Tipos.TORNEO:
        messages.error(request, 'Las categorías competitivas solo aplican a torneos.')
        return redirect('gestion:promociones_eventos')
    categoria = (
        get_object_or_404(CategoriaEvento, id=categoria_id, evento=evento)
        if categoria_id else None
    )
    form = CategoriaEventoForm(request.POST or None, instance=categoria)
    if request.method == 'POST' and form.is_valid():
        categoria_guardada = form.save(commit=False)
        categoria_guardada.evento = evento
        categoria_guardada.save()
        messages.success(request, 'Categoría del torneo guardada correctamente.')
        return redirect('gestion:promociones_eventos')
    return render(request, 'gestion/publicacion_formulario.html', {
        'form': form,
        'titulo': (
            f'Editar categoría · {evento.nombre}'
            if categoria else f'Nueva categoría · {evento.nombre}'
        ),
        'icono': 'fa-layer-group',
    })


@staff_member_required
def inscripciones_evento(request, evento_id):
    evento = get_object_or_404(
        Evento.objects.prefetch_related('categorias'), id=evento_id
    )
    inscripciones = evento.inscripciones.select_related(
        'alumno__user', 'pago', 'categoria_evento', 'academia_equipo'
    ).all()
    return render(request, 'gestion/inscripciones_evento.html', {
        'evento': evento,
        'inscripciones': inscripciones,
        'categorias_activas': evento.categorias.filter(activa=True),
    })


@staff_member_required
@transaction.atomic
def editar_inscripcion_evento(request, inscripcion_id):
    inscripcion = get_object_or_404(
        InscripcionEvento.objects.select_for_update().select_related(
            'evento', 'categoria_evento', 'academia_equipo'
        ),
        id=inscripcion_id,
        evento__tipo=Evento.Tipos.TORNEO,
    )
    form = EditarInscripcionEventoForm(
        request.POST or None,
        request.FILES or None,
        instance=inscripcion,
        evento=inscripcion.evento,
    )
    if request.method == 'POST' and form.is_valid():
        editada = form.save(commit=False)
        editada.participante_documento = editada.participante_documento.strip()
        if inscripcion.evento.alcance_torneo == Evento.AlcancesTorneo.ABIERTO:
            nombre_academia = editada.academia_origen.strip()
            academia = AcademiaCompetidora.objects.filter(
                nombre__iexact=nombre_academia
            ).first()
            if not academia:
                academia = AcademiaCompetidora.objects.create(
                    nombre=nombre_academia,
                    logo=form.cleaned_data.get('logo_academia'),
                )
            elif form.cleaned_data.get('logo_academia'):
                academia.logo = form.cleaned_data['logo_academia']
                academia.save(update_fields=['logo', 'actualizada'])
            editada.academia_equipo = academia
        else:
            academia, _ = AcademiaCompetidora.objects.get_or_create(
                nombre='Galeras BJJ'
            )
            editada.academia_origen = 'Galeras BJJ'
            editada.academia_equipo = academia
        editada.categoria = str(editada.categoria_evento)
        editada.save()
        messages.success(
            request,
            f'Los datos de {editada.participante_nombre} fueron actualizados.',
        )
        return redirect(
            'gestion:inscripciones_evento', evento_id=inscripcion.evento_id
        )
    return render(request, 'gestion/editar_inscripcion_evento.html', {
        'evento': inscripcion.evento,
        'inscripcion': inscripcion,
        'form': form,
    })


@staff_member_required
@require_POST
@transaction.atomic
def mover_inscripcion_categoria(request, inscripcion_id):
    inscripcion = get_object_or_404(
        InscripcionEvento.objects.select_for_update().select_related(
            'evento', 'categoria_evento'
        ),
        id=inscripcion_id,
        evento__tipo=Evento.Tipos.TORNEO,
    )
    categoria = get_object_or_404(
        CategoriaEvento,
        id=request.POST.get('categoria_evento'),
        evento=inscripcion.evento,
        activa=True,
    )
    observaciones = []
    nacimiento = inscripcion.fecha_nacimiento
    hoy = timezone.localdate()
    edad = hoy.year - nacimiento.year - (
        (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)
    )
    if categoria.edad_minima is not None and edad < categoria.edad_minima:
        observaciones.append('no cumple la edad mínima configurada')
    if categoria.edad_maxima is not None and edad > categoria.edad_maxima:
        observaciones.append('supera la edad máxima configurada')
    if inscripcion.peso is None:
        observaciones.append('no tiene peso registrado')
    else:
        if (
            categoria.peso_minimo is not None
            and inscripcion.peso < categoria.peso_minimo
        ):
            observaciones.append('su peso es inferior al mínimo configurado')
        if (
            categoria.peso_maximo is not None
            and inscripcion.peso > categoria.peso_maximo
        ):
            observaciones.append('su peso supera el máximo configurado')
    if (
        categoria.id != inscripcion.categoria_evento_id
        and categoria.cupos_disponibles == 0
    ):
        observaciones.append('la categoría supera el cupo configurado')
    inscripcion_duplicada = InscripcionEvento.objects.filter(
        evento=inscripcion.evento,
        participante_documento__iexact=inscripcion.participante_documento,
        categoria_evento=categoria,
    ).exclude(pk=inscripcion.pk).exclude(
        estado=InscripcionEvento.Estados.CANCELADA
    ).exists()
    if inscripcion_duplicada:
        messages.error(
            request,
            'No se puede mover porque el participante ya está inscrito en la '
            'categoría seleccionada.',
        )
    elif categoria.id == inscripcion.categoria_evento_id:
        messages.info(request, 'El participante ya pertenece a esa categoría.')
    else:
        inscripcion.categoria_evento = categoria
        inscripcion.categoria = str(categoria)
        inscripcion.save(update_fields=['categoria_evento', 'categoria', 'actualizada'])
        if observaciones:
            messages.warning(
                request,
                f'{inscripcion.participante_nombre} fue movido manualmente a '
                f'{categoria}. Revisa: ' + '; '.join(observaciones) + '.',
            )
        else:
            messages.success(
                request,
                f'{inscripcion.participante_nombre} fue movido a {categoria}.',
            )
    return redirect('gestion:inscripciones_evento', evento_id=inscripcion.evento_id)


def aplicar_promocion(request, promocion_id):
    promocion = get_object_or_404(
        Promocion.objects.select_related('plan'), id=promocion_id
    )
    if not promocion.vigente:
        messages.error(request, 'Esta promoción ya no está disponible.')
        return redirect('gestion:home_publica')
    form = AplicarPromocionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        usuario = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if not usuario or not hasattr(usuario, 'perfil_alumno'):
            form.add_error(None, 'Usuario o contraseña incorrectos.')
        else:
            alumno = usuario.perfil_alumno
            usos = AplicacionPromocion.objects.filter(
                promocion=promocion,
            ).exclude(estado=AplicacionPromocion.Estados.RECHAZADA)
            if promocion.un_uso_por_alumno and usos.filter(alumno=alumno).exists():
                form.add_error(None, 'Ya utilizaste o solicitaste esta promoción.')
            elif promocion.maximo_usos and usos.count() >= promocion.maximo_usos:
                form.add_error(None, 'La promoción alcanzó el máximo de aplicaciones.')
            elif promocion.publico == Promocion.Publicos.ACTIVOS and alumno.estado != Alumno.Estados.ACTIVO:
                form.add_error(None, 'Esta promoción es exclusiva para estudiantes activos.')
            elif promocion.publico == Promocion.Publicos.NUEVOS and alumno.suscripciones.exists():
                form.add_error(None, 'Esta promoción es exclusiva para estudiantes nuevos.')
            else:
                with transaction.atomic():
                    pago = Pago(
                        alumno=alumno,
                        plan=promocion.plan,
                        promocion=promocion,
                        tipo=Pago.Tipos.PROMOCION,
                        metodo_qr=form.cleaned_data['metodo_qr'],
                        valor=promocion.precio_aplicado,
                        comprobante=form.cleaned_data['comprobante'],
                        referencia_pago=form.cleaned_data['referencia_pago'],
                        pagador_nombre=alumno.nombre_acudiente or str(alumno),
                        pagador_documento=alumno.documento_acudiente or alumno.documento,
                        pagador_correo=alumno.user.email,
                    )
                    marcar_posible_duplicado(pago)
                    pago.save()
                    AplicacionPromocion.objects.create(
                        promocion=promocion, alumno=alumno, pago=pago
                    )
                messages.success(
                    request,
                    'Solicitud recibida. El pago quedó pendiente de revisión.',
                )
                return redirect('gestion:home_publica')
    return render(request, 'gestion/aplicar_promocion.html', {
        'promocion': promocion, 'form': form,
    })


def inscribirse_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id, activo=True)
    if (
        evento.tipo == Evento.Tipos.TORNEO
        and (
            not evento.consentimiento_evento.strip()
            or (
                evento.publico != Evento.Publicos.MENORES
                and not evento.reglamento_adultos.strip()
            )
            or (
                evento.publico != Evento.Publicos.ADULTOS
                and not evento.reglamento_menores.strip()
            )
        )
    ):
        messages.error(
            request,
            'Este torneo todavía no tiene completos el consentimiento y sus reglamentos.',
        )
        return redirect('gestion:home_publica')
    if not evento.disponible:
        messages.error(request, 'Las inscripciones para este evento no están disponibles.')
        return redirect('gestion:home_publica')
    alumno_interno = None
    if (
        evento.tipo == Evento.Tipos.TORNEO
        and evento.alcance_torneo == Evento.AlcancesTorneo.INTERNO
        and request.method == 'POST'
    ):
        alumno_interno = Alumno.objects.select_related('user').filter(
            documento__iexact=request.POST.get('participante_documento', '').strip()
        ).first()
    form = InscripcionEventoForm(
        request.POST or None, request.FILES or None,
        evento=evento, alumno_interno=alumno_interno,
    )
    if request.method == 'POST' and form.is_valid():
        alumno = alumno_interno or Alumno.objects.filter(
            documento__iexact=form.cleaned_data['participante_documento']
        ).select_related('user').first()
        if evento.publico == Evento.Publicos.ESTUDIANTES and not alumno:
            form.add_error('participante_documento', 'Este evento es exclusivo para estudiantes.')
        else:
            inscripciones_previas = InscripcionEvento.objects.filter(
                evento=evento,
                participante_documento__iexact=(
                    form.cleaned_data['participante_documento']
                ),
            ).exclude(estado=InscripcionEvento.Estados.CANCELADA)
            categoria_elegida = form.cleaned_data.get('categoria_evento')
            error_inscripcion = None
            if evento.tipo == Evento.Tipos.TORNEO:
                if inscripciones_previas.filter(
                    categoria_evento=categoria_elegida
                ).exists():
                    error_inscripcion = (
                        'Este participante ya está inscrito en esta categoría.'
                    )
                elif inscripciones_previas.count() >= 2:
                    error_inscripcion = (
                        'Cada participante puede inscribirse como máximo en dos categorías.'
                    )
                elif (
                    inscripciones_previas.exists()
                    and categoria_elegida.tipo_categoria
                    == CategoriaEvento.TiposCategoria.REGULAR
                ):
                    error_inscripcion = (
                        'La segunda inscripción debe ser en una categoría superior '
                        'o absoluta.'
                    )
            elif inscripciones_previas.exists():
                error_inscripcion = 'Este participante ya está inscrito en el evento.'
            if error_inscripcion:
                form.add_error('categoria_evento', error_inscripcion)
            else:
                precio = evento.precio_estudiante if alumno else evento.precio_externo
                with transaction.atomic():
                    inscripcion = form.save(commit=False)
                    inscripcion.evento = evento
                    inscripcion.alumno = alumno
                    if evento.tipo == Evento.Tipos.TORNEO:
                        inscripcion.texto_consentimiento = evento.consentimiento_evento
                        nacimiento = form.cleaned_data['fecha_nacimiento']
                        hoy = timezone.localdate()
                        edad = hoy.year - nacimiento.year - (
                            (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)
                        )
                        inscripcion.texto_reglamento = (
                            evento.reglamento_menores
                            if edad < 18 else evento.reglamento_adultos
                        )
                        inscripcion.fecha_firma = timezone.now()
                        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
                        inscripcion.ip_firma = (
                            forwarded_for.split(',')[0].strip()
                            if forwarded_for else request.META.get('REMOTE_ADDR')
                        )
                        if evento.alcance_torneo == Evento.AlcancesTorneo.ABIERTO:
                            academia = AcademiaCompetidora.objects.filter(
                                nombre__iexact=inscripcion.academia_origen.strip()
                            ).first()
                            if not academia:
                                academia = AcademiaCompetidora.objects.create(
                                    nombre=inscripcion.academia_origen.strip(),
                                    logo=form.cleaned_data.get('logo_academia'),
                                )
                            elif not academia.logo and form.cleaned_data.get('logo_academia'):
                                academia.logo = form.cleaned_data['logo_academia']
                                academia.save(update_fields=['logo', 'actualizada'])
                            inscripcion.academia_equipo = academia
                        elif alumno:
                            academia, _ = AcademiaCompetidora.objects.get_or_create(
                                nombre='Galeras BJJ'
                            )
                            inscripcion.academia_equipo = academia
                            from registros_legales.models import RegistroLegalEstudiante
                            registro = RegistroLegalEstudiante.objects.filter(
                                documento__iexact=alumno.documento,
                                estado=RegistroLegalEstudiante.Estados.APROBADO,
                                foto__isnull=False,
                            ).exclude(foto='').order_by('-actualizado').first()
                            if registro:
                                inscripcion.foto_participante.name = registro.foto.name
                    if inscripcion.categoria_evento_id:
                        inscripcion.categoria = str(inscripcion.categoria_evento)
                    if evento.cupos_disponibles == 0:
                        inscripcion.estado = InscripcionEvento.Estados.LISTA_ESPERA
                    elif precio == 0:
                        inscripcion.estado = InscripcionEvento.Estados.CONFIRMADA
                    pago = None
                    if precio > 0:
                        pagador_nombre = (
                            inscripcion.acudiente_nombre or inscripcion.participante_nombre
                        )
                        pagador_documento = (
                            inscripcion.acudiente_documento
                            or inscripcion.participante_documento
                        )
                        pago = Pago(
                            alumno=alumno,
                            tipo=Pago.Tipos.EVENTO,
                            metodo_qr=form.cleaned_data['metodo_qr'],
                            valor=precio,
                            comprobante=form.cleaned_data['comprobante'],
                            referencia_pago=form.cleaned_data['referencia_pago'],
                            pagador_nombre=pagador_nombre,
                            pagador_documento=pagador_documento,
                            pagador_correo=inscripcion.correo,
                            concepto_detalle=f'{evento.get_tipo_display()}: {evento.nombre}',
                        )
                        marcar_posible_duplicado(pago)
                        pago.save()
                    inscripcion.pago = pago
                    inscripcion.save()
                messages.success(
                    request,
                    'Inscripción recibida.'
                    + (' El pago quedó pendiente de revisión.' if pago else ' Tu cupo quedó confirmado.'),
                )
                return redirect('gestion:home_publica')
    if request.method == 'POST' and form.errors and 'firma_base64' in form.fields:
        datos_sin_firma = form.data.copy()
        datos_sin_firma['firma_base64'] = ''
        form.data = datos_sin_firma
    return render(request, 'gestion/inscripcion_evento.html', {
        'evento': evento, 'form': form,
    })


def datos_estudiante_torneo(request, evento_id):
    evento = get_object_or_404(
        Evento,
        id=evento_id,
        tipo=Evento.Tipos.TORNEO,
        alcance_torneo=Evento.AlcancesTorneo.INTERNO,
        activo=True,
    )
    documento = request.GET.get('documento', '').strip()
    alumno = Alumno.objects.select_related('user').filter(
        documento__iexact=documento
    ).first()
    if not alumno:
        return JsonResponse(
            {'encontrado': False, 'mensaje': 'No encontramos este documento.'},
            status=404,
        )
    faltantes = []
    if not alumno.fecha_nacimiento:
        faltantes.append('fecha de nacimiento')
    if not alumno.user.email:
        faltantes.append('correo')
    if not alumno.user.telefono:
        faltantes.append('teléfono')
    return JsonResponse({
        'encontrado': True,
        'nombre': str(alumno),
        'fecha_nacimiento': (
            alumno.fecha_nacimiento.isoformat() if alumno.fecha_nacimiento else ''
        ),
        'correo': alumno.user.email or '',
        'telefono': alumno.user.telefono or '',
        'acudiente_nombre': alumno.nombre_acudiente or '',
        'ficha_completa': not faltantes,
        'mensaje': (
            'Ficha lista para la inscripción.' if not faltantes
            else 'La administración debe completar: ' + ', '.join(faltantes) + '.'
        ),
        'evento': evento.nombre,
    })


def descargar_comprobante_pago(request, token):
    pago = get_object_or_404(
        Pago.objects.select_related('alumno__user', 'suscripcion', 'metodo_qr'),
        token_comprobante=token,
        estado=Pago.Estados.APROBADO,
    )
    respuesta = HttpResponse(
        generar_pdf_comprobante_pago(pago), content_type='application/pdf'
    )
    respuesta['Content-Disposition'] = (
        f'attachment; filename="comprobante-{pago.numero_comprobante}.pdf"'
    )
    return respuesta


@staff_member_required
@require_POST
def reenviar_comprobante_pago(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id, estado=Pago.Estados.APROBADO)
    try:
        enviar_comprobante_pago(pago)
        messages.success(request, 'Comprobante reenviado correctamente.')
    except Exception as error:
        pago.error_envio_comprobante = str(error)[:500]
        pago.save(update_fields=['error_envio_comprobante'])
        messages.error(request, f'No fue posible enviar el correo: {error}')
    return redirect('gestion:lista_pagos')


# VISTA PARA AGREGAR MUSICA

@staff_member_required
def configurar_home(request):

    config_home = ConfiguracionHome.objects.filter(
        activo=True
    ).first()

    if not config_home:
        config_home = ConfiguracionHome.objects.create(
            activo=True
        )

    if request.method == 'POST':
        form = ConfiguracionHomeForm(
            request.POST,
            request.FILES,
            instance=config_home
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Configuración de la home actualizada correctamente.'
            )

            return redirect('gestion:configurar_home')

        else:
            messages.error(
                request,
                'No se pudo guardar. Revisa los errores del formulario.'
            )

    else:
        form = ConfiguracionHomeForm(
            instance=config_home
        )

    return render(request, 'gestion/configurar_home.html', {
        'form': form,
        'config_home': config_home,
    })

# VISTA PARA CONFIRMAR CLASE DESDE HOME


@require_POST
def confirmar_clase_home(request):

    clase_id = request.POST.get('clase_id')
    username = request.POST.get('username')
    password = request.POST.get('password')

    clase = get_object_or_404(
        ClaseProgramada,
        id=clase_id,
        activa=True
    )

    user = authenticate(
        request,
        username=username,
        password=password
    )

    if user is None:
        messages.error(request, 'Usuario o contraseña incorrectos.')
        return redirect('gestion:home_publica')

    if not hasattr(user, 'perfil_alumno'):
        messages.error(request, 'Este usuario no está registrado como alumno.')
        return redirect('gestion:home_publica')

    alumno = user.perfil_alumno
    ahora = timezone.localtime()
    hoy = ahora.date()

    dias_semana = {
        0: ClaseProgramada.DiasSemana.LUNES,
        1: ClaseProgramada.DiasSemana.MARTES,
        2: ClaseProgramada.DiasSemana.MIERCOLES,
        3: ClaseProgramada.DiasSemana.JUEVES,
        4: ClaseProgramada.DiasSemana.VIERNES,
        5: ClaseProgramada.DiasSemana.SABADO,
        6: ClaseProgramada.DiasSemana.DOMINGO,
    }
    inicio_clase = timezone.make_aware(
        datetime.combine(hoy, clase.hora_inicio),
        timezone.get_current_timezone(),
    )
    ventana_inicio = inicio_clase - timedelta(minutes=20)
    ventana_fin = inicio_clase + timedelta(minutes=30)

    if clase.dia != dias_semana[ahora.weekday()] or not (
        ventana_inicio <= ahora <= ventana_fin
    ):
        messages.error(
            request,
            'Esta clase ya no está disponible para confirmar. Actualiza la página y selecciona la clase vigente.',
        )
        return redirect('gestion:home_publica')

    suscripcion = Suscripcion.objects.filter(
        alumno=alumno,
        estado='ACTIVA'
    ).select_related('plan').order_by('-fecha_vencimiento').first()

    if not suscripcion:
        messages.error(
            request,
            'No tienes una suscripción activa para confirmar clases.'
        )
        return redirect('gestion:home_publica')

    if suscripcion.fecha_inicio > hoy:
        messages.error(
            request,
            f'Tu suscripción inicia el {suscripcion.fecha_inicio}. Aún no puedes confirmar clases.'
        )
        return redirect('gestion:home_publica')

    if suscripcion.fecha_vencimiento < hoy:
        messages.error(
            request,
            f'Tu suscripción venció el {suscripcion.fecha_vencimiento}. Debes renovar.'
        )
        return redirect('gestion:home_publica')

    if not suscripcion:
        messages.error(
            request,
            'No tienes una suscripción activa para confirmar clases.'
        )
        return redirect('gestion:home_publica')

    plan = suscripcion.plan

    if not plan_permite_disciplina(plan, clase.disciplina):
        messages.error(
            request,
            'La disciplina de esta clase no está incluida en tu plan.'
        )
        return redirect('gestion:home_publica')

    ya_confirmo = AsistenciaClase.objects.filter(
        alumno=alumno,
        clase=clase,
        fecha_clase=hoy,
        estado=AsistenciaClase.Estados.CONFIRMADA,
    ).exists()

    clases_consumidas = AsistenciaClase.objects.filter(
        alumno=alumno,
        estado=AsistenciaClase.Estados.CONFIRMADA,
        fecha_clase__gte=suscripcion.fecha_inicio,
        fecha_clase__lte=suscripcion.fecha_vencimiento
    ).count()

    if (
        not plan.asistencia_ilimitada
        and not ya_confirmo
        and clases_consumidas >= plan.clases_mes
    ):
        messages.error(
            request,
            f'Ya consumiste tus {plan.clases_mes} clases disponibles de este plan.'
        )
        return redirect('gestion:home_publica')

    total_asistentes = AsistenciaClase.objects.filter(
        clase=clase,
        fecha_clase=hoy,
        estado=AsistenciaClase.Estados.CONFIRMADA,
    ).count()

    if not ya_confirmo and total_asistentes >= clase.cupo_maximo:
        messages.error(request, 'No hay cupos disponibles para esta clase.')
        return redirect('gestion:home_publica')

    asistencia, creada = AsistenciaClase.objects.get_or_create(
        alumno=alumno,
        clase=clase,
        fecha_clase=hoy,
        defaults={
            'estado': AsistenciaClase.Estados.CONFIRMADA,
            'fecha_confirmacion': ahora,
        }
    )

    if creada:
        if plan.asistencia_ilimitada:
            messages.success(request, 'Clase confirmada correctamente.')
        else:
            restantes = plan.clases_mes - (clases_consumidas + 1)
            messages.success(
                request,
                f'Clase confirmada correctamente. Te quedan {restantes} clases disponibles.'
            )
    else:
        messages.info(request, 'Ya habías confirmado esta clase.')

    return redirect('gestion:home_publica')

# VISTA PARA CONFIGURAR HOME


@staff_member_required
def configuraciones(request):
    return render(request, 'gestion/configuraciones.html')


@staff_member_required
def configurar_cuentas(request, cuenta_id=None):
    cuenta = None
    if cuenta_id is not None:
        cuenta = get_object_or_404(CuentaFinanciera, id=cuenta_id)

    if request.method == 'POST':
        form = CuentaFinancieraForm(request.POST, instance=cuenta)
        if form.is_valid():
            cuenta_guardada = form.save()
            accion = 'actualizada' if cuenta else 'creada'
            messages.success(
                request,
                f'Cuenta "{cuenta_guardada.nombre}" {accion} correctamente.'
            )
            return redirect('gestion:configurar_cuentas')
    else:
        form = CuentaFinancieraForm(instance=cuenta)

    cuentas = list(CuentaFinanciera.objects.all().order_by('-activa', 'nombre'))
    for cuenta_financiera in cuentas:
        cuenta_financiera.saldo_calculado = cuenta_financiera.saldo_actual

    return render(request, 'gestion/configurar_cuentas.html', {
        'form': form,
        'cuentas': cuentas,
        'cuenta_editando': cuenta,
    })


# VISTAS DE CONFIGURACION DE DIAS Y HORAS

@staff_member_required
def configurar_horario(request):

    clases = ClaseProgramada.objects.select_related(
        'instructor'
    ).order_by(
        'dia',
        'hora_inicio'
    )

    return render(
        request,
        'gestion/configurar_horario.html',
        {
            'clases': clases
        }
    )

# CONFIGURAR HORARIOS


@staff_member_required
def crear_dia_horario(request):
    if request.method == 'POST':
        form = DiaHorarioForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Día agregado correctamente.')

    return redirect('gestion:configurar_horario')


@staff_member_required
def crear_hora_horario(request):
    if request.method == 'POST':
        form = HoraHorarioForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Hora agregada correctamente.')


# VISTA DE CRONOMETRO

@login_required
def cronometro_lucha(request):
    torneos = Evento.objects.filter(
        tipo=Evento.Tipos.TORNEO,
        activo=True,
    ).order_by('-fecha_inicio')
    evento_seleccionado = None
    categoria_seleccionada = None
    categorias_torneo = CategoriaEvento.objects.none()
    participantes_llave = []
    logos_llave = {}
    version_llave = 'manual'
    if request.user.is_superuser:
        evento_id = request.GET.get('evento')
        categoria_id = request.GET.get('categoria')
        if evento_id:
            evento_seleccionado = torneos.filter(id=evento_id).first()
        if evento_seleccionado:
            categorias_torneo = evento_seleccionado.categorias.filter(
                activa=True
            )
        if categoria_id and evento_seleccionado:
            categoria_seleccionada = categorias_torneo.filter(id=categoria_id).first()
        if categoria_seleccionada:
            participantes = list(
                categoria_seleccionada.inscripciones.filter(
                    estado=InscripcionEvento.Estados.CONFIRMADA,
                ).select_related('academia_equipo').order_by('participante_nombre')
            )
            participantes_llave = [
                f'{item.participante_nombre} — {item.academia_origen or "Galeras BJJ"}'
                for item in participantes
            ]
            for item, etiqueta in zip(participantes, participantes_llave):
                if item.academia_equipo and item.academia_equipo.logo:
                    logos_llave[etiqueta] = item.academia_equipo.logo.url
                elif not item.academia_origen:
                    logos_llave[etiqueta] = static('img/galeras-bjj-logo.png')
            version_llave = hashlib.sha256(
                '|'.join(
                    f'{item.id}:{item.participante_nombre}:'
                    f'{item.academia_origen or "Galeras BJJ"}:'
                    f'{logos_llave.get(etiqueta, "")}'
                    for item, etiqueta in zip(participantes, participantes_llave)
                ).encode('utf-8')
            ).hexdigest()[:12]
    return render(request, 'gestion/cronometro_lucha.html', {
        'torneos_llaves': torneos,
        'evento_llaves': evento_seleccionado,
        'categorias_llaves': categorias_torneo,
        'categoria_llaves': categoria_seleccionada,
        'participantes_llave': participantes_llave,
        'logos_llave': logos_llave,
        'version_llave': version_llave,
    })


def _clase_tv_payload():
    ahora = timezone.localtime()
    dias = ['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO']
    clases = ClaseProgramada.objects.filter(
        activa=True,
        dia=dias[ahora.weekday()],
    ).select_related('instructor').order_by('hora_inicio')
    clase = clases.filter(
        hora_inicio__lte=(ahora + timedelta(minutes=20)).time(),
        hora_fin__gte=ahora.time(),
    ).first()
    if not clase:
        clase = clases.filter(hora_inicio__gt=ahora.time()).first()
    if not clase:
        return {'active': False, 'title': 'SIN CLASE PROGRAMADA', 'attendees': [], 'total': 0}

    asistencias = AsistenciaClase.objects.filter(
        clase=clase,
        fecha_clase=ahora.date(),
        estado=AsistenciaClase.Estados.CONFIRMADA,
    ).select_related('alumno__user').order_by('alumno__user__first_name')
    nombres = [str(asistencia.alumno).upper() for asistencia in asistencias]
    return {
        'active': clase.hora_inicio <= ahora.time() <= clase.hora_fin,
        'title': (clase.titulo or clase.get_disciplina_display()).upper(),
        'discipline': clase.get_disciplina_display().upper(),
        'time': f'{clase.hora_inicio:%H:%M} - {clase.hora_fin:%H:%M}',
        'instructor': str(clase.instructor).upper(),
        'attendees': nombres,
        'total': len(nombres),
        'capacity': clase.cupo_maximo,
    }


def _estado_tv_actual(sesion, guardar=True):
    estado = {**estado_tv_inicial(), **(sesion.estado or {})}
    cambio = False
    ahora = timezone.now()

    if estado.get('preparing') and estado.get('preparation_started_at'):
        inicio_preparacion = datetime.fromisoformat(estado['preparation_started_at'])
        if timezone.is_naive(inicio_preparacion):
            inicio_preparacion = timezone.make_aware(inicio_preparacion)
        transcurrido = int((ahora - inicio_preparacion).total_seconds())
        preparacion_restante = max(
            0, int(estado.get('preparation_seconds', 5)) - transcurrido
        )
        if preparacion_restante > 0:
            estado['display_remaining'] = preparacion_restante
            estado['display_phase'] = 'preparation'
        else:
            estado['preparing'] = False
            estado['preparation_started_at'] = None
            estado['running'] = True
            estado['started_at'] = ahora.isoformat()
            estado['remaining'] = estado['duration']
            estado['warning_done'] = False
            estado['sound_event'] = {
                'type': 'bell', 'id': ahora.isoformat()
            }
            estado['display_remaining'] = estado['duration']
            estado['display_phase'] = 'round'
            cambio = True

    if estado['running'] and estado.get('started_at'):
        inicio = datetime.fromisoformat(estado['started_at'])
        if timezone.is_naive(inicio):
            inicio = timezone.make_aware(inicio)
        transcurrido = int((ahora - inicio).total_seconds())
        restante = max(0, int(estado['remaining']) - transcurrido)
        if 0 < restante <= 10 and not estado.get('warning_done'):
            estado['warning_done'] = True
            estado['sound_event'] = {
                'type': 'claps', 'id': ahora.isoformat()
            }
            cambio = True
        if restante == 0:
            estado['remaining'] = 0
            estado['running'] = False
            estado['started_at'] = None
            estado['sound_event'] = {
                'type': 'bell', 'id': ahora.isoformat()
            }
            estado['display_phase'] = 'ended'
            cambio = True
        else:
            estado['display_remaining'] = restante
            estado['display_phase'] = 'round'
    if cambio and guardar:
        estado_guardado = {
            key: value for key, value in estado.items()
            if key not in {'display_remaining', 'display_phase'}
        }
        sesion.estado = estado_guardado
        sesion.save(update_fields=['estado', 'actualizada'])
    estado.setdefault('display_remaining', estado['remaining'])
    estado.setdefault('display_phase', 'stopped')
    return estado


def _youtube_video_id(value):
    """Obtiene un identificador seguro desde enlaces comunes de YouTube."""
    value = (value or '').strip()
    parsed = urlparse(value if '://' in value else f'https://{value}')
    host = parsed.netloc.lower().split(':')[0]
    video_id = None
    if host in {'youtu.be', 'www.youtu.be'}:
        video_id = parsed.path.strip('/').split('/')[0]
    elif host in {
        'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'
    }:
        if parsed.path == '/watch':
            video_id = parse_qs(parsed.query).get('v', [None])[0]
        elif parsed.path.startswith(('/embed/', '/shorts/', '/live/')):
            parts = parsed.path.strip('/').split('/')
            video_id = parts[1] if len(parts) > 1 else None
    allowed = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
    if not video_id or len(video_id) != 11 or any(c not in allowed for c in video_id):
        return None
    return video_id


def _youtube_event(command):
    return {'type': command, 'id': timezone.now().isoformat()}


def _resolver_bye_tv(match):
    p1, p2 = match.get('p1'), match.get('p2')
    if not p1 or not p2:
        return None
    if p1 == '__BYE__' and p2 == '__BYE__':
        return '__BYE__'
    if p1 == '__BYE__':
        return p2
    if p2 == '__BYE__':
        return p1
    return match.get('winner') if match.get('winner') in {p1, p2} else None


def _propagar_llave_tv(bracket):
    for match in bracket['rounds'][0]:
        match['winner'] = _resolver_bye_tv(match)
    for round_index in range(1, len(bracket['rounds'])):
        previous = bracket['rounds'][round_index - 1]
        for match_index, match in enumerate(bracket['rounds'][round_index]):
            match['p1'] = previous[match_index * 2]['winner']
            match['p2'] = previous[match_index * 2 + 1]['winner']
            match['winner'] = _resolver_bye_tv(match)


def _crear_llave_tv(names, configured_size):
    capacity = 1
    while capacity < configured_size:
        capacity *= 2
    bye_count = capacity - len(names)
    first_round = []
    name_index = 0
    for match_index in range(capacity // 2):
        p1 = names[name_index] if name_index < len(names) else '__BYE__'
        name_index += 1
        if match_index < bye_count:
            p2 = '__BYE__'
        else:
            p2 = names[name_index] if name_index < len(names) else '__BYE__'
            name_index += 1
        first_round.append({'p1': p1, 'p2': p2, 'winner': None})
    rounds = [first_round]
    match_count = capacity // 2
    while match_count > 1:
        match_count //= 2
        rounds.append([
            {'p1': None, 'p2': None, 'winner': None}
            for _ in range(match_count)
        ])
    bracket = {'size': configured_size, 'names': names, 'rounds': rounds}
    _propagar_llave_tv(bracket)
    return bracket


@staff_member_required
def control_tv(request):
    sesion = SesionTV.objects.filter(
        propietario=request.user,
        activa=True,
        expira_en__gt=timezone.now(),
    ).first()
    if not sesion:
        while True:
            codigo = f'{secrets.randbelow(1000000):06d}'
            if not SesionTV.objects.filter(codigo=codigo).exists():
                break
        sesion = SesionTV.objects.create(
            propietario=request.user,
            codigo=codigo,
            # La vigencia real termina al cerrar sesión. Esta fecha lejana se
            # conserva por compatibilidad con sesiones y migraciones anteriores.
            expira_en=timezone.now() + timedelta(days=3650),
        )
    return render(request, 'gestion/control_tv.html', {
        'sesion_tv': sesion,
        'tv_url': request.build_absolute_uri(
            reverse('gestion:pantalla_tv', kwargs={'token': sesion.token})
        ),
    })


def vincular_tv(request):
    error = None
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip()
        sesion = SesionTV.objects.filter(
            codigo=codigo,
            activa=True,
            expira_en__gt=timezone.now(),
        ).first()
        if sesion:
            return redirect('gestion:pantalla_tv', token=sesion.token)
        error = 'El código no existe o ya venció.'
    return render(request, 'gestion/vincular_tv.html', {'error': error})


def pantalla_tv(request, token):
    sesion = get_object_or_404(SesionTV, token=token)
    if not sesion.vigente:
        raise Http404('Sesión TV vencida')
    return render(request, 'gestion/pantalla_tv.html', {'sesion_tv': sesion})


def estado_tv(request, token):
    sesion = get_object_or_404(SesionTV, token=token)
    if not sesion.vigente:
        return JsonResponse({'error': 'Sesión vencida'}, status=410)
    return JsonResponse({
        'state': _estado_tv_actual(sesion),
        'class': _clase_tv_payload(),
        'server_time': timezone.localtime().isoformat(),
    })


@staff_member_required
@require_POST
def accion_tv(request, token):
    sesion = get_object_or_404(SesionTV, token=token, propietario=request.user)
    if not sesion.vigente:
        return JsonResponse({'error': 'Sesión vencida'}, status=410)
    estado = _estado_tv_actual(sesion, guardar=False)
    display_remaining = estado.pop('display_remaining', estado['remaining'])
    display_phase = estado.pop('display_phase', 'stopped')
    if display_phase != 'preparation':
        estado['remaining'] = display_remaining
    accion = request.POST.get('action', '')

    if accion == 'mode':
        estado['mode'] = request.POST.get('value') if request.POST.get('value') in {'overview', 'timer', 'bracket'} else 'overview'
    elif accion == 'start' and estado['remaining'] > 0 and not estado['running']:
        inicio_nuevo = estado['remaining'] == estado['duration']
        if inicio_nuevo:
            estado['preparing'] = True
            estado['preparation_started_at'] = timezone.now().isoformat()
            estado['running'] = False
            estado['started_at'] = None
            estado['warning_done'] = False
            estado['sound_event'] = None
        else:
            estado['preparing'] = False
            estado['preparation_started_at'] = None
            estado['running'] = True
            estado['started_at'] = timezone.now().isoformat()
    elif accion == 'pause':
        estado['preparing'] = False
        estado['preparation_started_at'] = None
        estado['running'] = False
        estado['started_at'] = None
    elif accion == 'reset':
        mode = estado.get('mode', 'timer')
        bracket = estado.get('bracket')
        duration = estado.get('duration', 300)
        youtube = {
            key: value for key, value in estado.items()
            if key.startswith('youtube_')
        }
        estado = estado_tv_inicial()
        estado['mode'] = mode
        estado['bracket'] = bracket
        estado['duration'] = duration
        estado['remaining'] = duration
        estado.update(youtube)
    elif accion == 'duration':
        minutos = max(1, min(60, int(request.POST.get('value', 5))))
        estado['duration'] = minutos * 60
        estado['remaining'] = estado['duration']
        estado['preparing'] = False
        estado['preparation_started_at'] = None
        estado['running'] = False
        estado['started_at'] = None
    elif accion == 'names':
        estado['red_name'] = request.POST.get('red_name', '')[:60].upper() or 'COMPETIDOR ROJO'
        estado['blue_name'] = request.POST.get('blue_name', '')[:60].upper() or 'COMPETIDOR AZUL'
    elif accion == 'youtube_load':
        video_id = _youtube_video_id(request.POST.get('value'))
        if not video_id:
            return JsonResponse({'error': 'El enlace de YouTube no es válido.'}, status=400)
        estado['youtube_video_id'] = video_id
        estado['youtube_visible'] = True
        estado['youtube_command'] = _youtube_event('load')
    elif accion in {'youtube_play', 'youtube_pause', 'youtube_stop'}:
        if not estado.get('youtube_video_id'):
            return JsonResponse({'error': 'Primero carga un video de YouTube.'}, status=400)
        estado['youtube_visible'] = True
        estado['youtube_command'] = _youtube_event(accion.removeprefix('youtube_'))
    elif accion == 'youtube_visibility':
        estado['youtube_visible'] = not estado.get('youtube_visible', False)
    elif accion == 'youtube_size':
        estado['youtube_size'] = (
            'large' if estado.get('youtube_size') == 'small' else 'small'
        )
    elif accion == 'youtube_volume':
        try:
            volume = int(request.POST.get('value', 35))
        except ValueError:
            volume = 35
        estado['youtube_volume'] = max(0, min(100, volume))
        estado['youtube_command'] = _youtube_event('volume')
    elif accion in {'red_points', 'blue_points', 'red_advantages', 'blue_advantages', 'red_penalties', 'blue_penalties'}:
        delta = 1 if request.POST.get('delta') == '1' else -1
        estado[accion] = max(0, int(estado.get(accion, 0)) + delta)
    elif accion == 'bracket_create':
        try:
            size = int(request.POST.get('size', 4))
        except ValueError:
            size = 4
        size = size if size in {4, 8, 10, 12, 16} else 4
        names = [
            name.strip().upper()[:60]
            for name in request.POST.get('names', '').splitlines()
            if name.strip()
        ][:size]
        if len(names) < 2 or len(set(names)) != len(names):
            return JsonResponse({'error': 'Ingresa al menos dos nombres diferentes.'}, status=400)
        estado['bracket'] = _crear_llave_tv(names, size)
        estado['mode'] = 'bracket'
    elif accion == 'bracket_winner':
        bracket = estado.get('bracket')
        try:
            round_index = int(request.POST.get('round'))
            match_index = int(request.POST.get('match'))
            winner = request.POST.get('winner', '')
            match = bracket['rounds'][round_index][match_index]
        except (TypeError, ValueError, IndexError, KeyError):
            return JsonResponse({'error': 'Combate no válido.'}, status=400)
        if winner not in {match.get('p1'), match.get('p2')} or winner == '__BYE__':
            return JsonResponse({'error': 'Ganador no válido.'}, status=400)
        match['winner'] = winner
        _propagar_llave_tv(bracket)
    elif accion == 'bracket_load':
        bracket = estado.get('bracket')
        try:
            round_index = int(request.POST.get('round'))
            match_index = int(request.POST.get('match'))
            match = bracket['rounds'][round_index][match_index]
            p1, p2 = match.get('p1'), match.get('p2')
        except (TypeError, ValueError, IndexError, KeyError):
            return JsonResponse({'error': 'Combate no válido.'}, status=400)
        if not p1 or not p2 or '__BYE__' in {p1, p2}:
            return JsonResponse({'error': 'Este combate aún no está listo.'}, status=400)
        duration = estado.get('duration', 300)
        youtube = {
            key: value for key, value in estado.items()
            if key.startswith('youtube_')
        }
        estado_nuevo = estado_tv_inicial()
        estado_nuevo['mode'] = 'timer'
        estado_nuevo['bracket'] = bracket
        estado_nuevo['duration'] = duration
        estado_nuevo['remaining'] = duration
        estado_nuevo.update(youtube)
        estado_nuevo['red_name'] = p1
        estado_nuevo['blue_name'] = p2
        estado_nuevo['active_match'] = {
            'round': round_index, 'match': match_index, 'p1': p1, 'p2': p2
        }
        estado = estado_nuevo
    elif accion == 'fight_winner':
        bracket = estado.get('bracket')
        active = estado.get('active_match')
        side = request.POST.get('side')
        if not bracket or not active or side not in {'red', 'blue'}:
            return JsonResponse({'error': 'No hay un combate de llave activo.'}, status=400)
        winner = active['p1'] if side == 'red' else active['p2']
        match = bracket['rounds'][active['round']][active['match']]
        match['winner'] = winner
        _propagar_llave_tv(bracket)
        estado['active_match'] = None
        estado['running'] = False
        estado['started_at'] = None
        estado['mode'] = 'bracket'
    elif accion == 'bracket_reset':
        estado['bracket'] = None
        estado['active_match'] = None
        estado['mode'] = 'bracket'

    if estado['running'] and accion != 'start':
        estado['started_at'] = timezone.now().isoformat()

    sesion.estado = estado
    sesion.save(update_fields=['estado', 'actualizada'])
    return JsonResponse({'state': _estado_tv_actual(sesion, guardar=False)})


@staff_member_required
@require_POST
def renovar_tv(request, token):
    sesion = get_object_or_404(SesionTV, token=token, propietario=request.user)
    sesion.expira_en = timezone.now() + timedelta(days=3650)
    sesion.activa = True
    sesion.save(update_fields=['expira_en', 'activa', 'actualizada'])
    return JsonResponse({'ok': True, 'expires': sesion.expira_en.isoformat()})
