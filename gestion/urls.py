from django.urls import path

from alumnos import admin
from . import views
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path, include
from django.contrib.auth import views as auth_views


app_name = 'gestion'

urlpatterns = [
    path('', views.home_publica, name='home_publica'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('alumnos/', views.lista_alumnos, name='lista_alumnos'),
    path('alumnos/crear/', views.crear_alumno, name='crear_alumno'),

    path('planes/', views.lista_planes, name='lista_planes'),
    path('planes/crear/', views.crear_plan, name='crear_plan'),

    path('suscripciones/', views.lista_suscripciones, name='lista_suscripciones'),
    path('suscripciones/crear/', views.crear_suscripcion, name='crear_suscripcion'),

    path('pagos/', views.lista_pagos, name='lista_pagos'),
    path('pagos/crear/', views.crear_pago, name='crear_pago'),
    path('pagos/<int:pago_id>/validar/',
         views.validar_pago, name='validar_pago'),

    path('alumnos/<int:alumno_id>/editar/',
         views.editar_alumno, name='editar_alumno'),
    path('alumnos/<int:alumno_id>/eliminar/',
         views.eliminar_alumno, name='eliminar_alumno'),

    path('planes/<int:plan_id>/editar/', views.editar_plan, name='editar_plan'),
    path('planes/<int:plan_id>/eliminar/',
         views.eliminar_plan, name='eliminar_plan'),

    path('suscripciones/<int:suscripcion_id>/editar/',
         views.editar_suscripcion, name='editar_suscripcion'),
    path('suscripciones/<int:suscripcion_id>/eliminar/',
         views.eliminar_suscripcion, name='eliminar_suscripcion'),

    path('horario/', views.horario_clases, name='horario_clases'),
    path('mi-asistencia/', views.mi_asistencia, name='mi_asistencia'),
    path('horario/<int:clase_id>/confirmar/',
         views.confirmar_asistencia, name='confirmar_asistencia'),
    path('horario/crear/', views.crear_clase, name='crear_clase'),
    path('horario/<int:clase_id>/editar/',
         views.editar_clase, name='editar_clase'),
    path(
        'clases/<int:clase_id>/eliminar/',
        views.eliminar_clase,
        name='eliminar_clase'
    ),
    path('horario/confirmar-kiosko/', views.confirmar_asistencia_kiosko,
         name='confirmar_asistencia_kiosko'),
    path('horario/<int:clase_id>/asistentes/',
         views.asistentes_clase, name='asistentes_clase'),

    path('pagos/alumno/registrar/', views.registrar_pago_alumno,
         name='registrar_pago_alumno'),

    path('alumnos/<int:alumno_id>/reset-password/',
         views.reset_password_alumno, name='reset_password_alumno'),

    path('finanzas/gasto/crear/', views.registrar_gasto, name='registrar_gasto'),

    path('finanzas/pago-programado/crear/',
         views.crear_pago_programado, name='crear_pago_programado'),
    path('finanzas/pago-programado/<int:pago_id>/pagar/',
         views.pagar_pago_programado, name='pagar_pago_programado'),

    path('finanzas/detalle/', views.detalle_financiero, name='detalle_financiero'),
    path('finanzas/transferencia/crear/',
         views.registrar_transferencia, name='registrar_transferencia'),

    path('registros-legales/', views.lista_registros_legales,
         name='lista_registros_legales'),
    path('registros-legales/<int:registro_id>/',
         views.detalle_registro_legal, name='detalle_registro_legal'),
    path('registros-legales/<int:registro_id>/aprobar/',
         views.aprobar_registro_legal, name='aprobar_registro_legal'),
    path('registros-legales/<int:registro_id>/rechazar/',
         views.rechazar_registro_legal, name='rechazar_registro_legal'),
    path('registros-legales/<int:registro_id>/pdf/',
         views.descargar_pdf_registro_legal, name='descargar_pdf_registro_legal'),

    path('cambiar-password-obligatorio/', views.cambio_password_obligatorio,
         name='cambio_password_obligatorio'),
    path('mi-cuenta/cambiar-usuario/', views.cambiar_usuario,
         name='cambiar_usuario'),
    path(
        'configurar-home/',
        views.configurar_home,
        name='configurar_home'
    ),
    path(
        'confirmar-clase-home/',
        views.confirmar_clase_home,
        name='confirmar_clase_home'
    ),
    path(
        'configuraciones/',
        views.configuraciones,
        name='configuraciones'
    ),
    path(
        'configurar-horario/',
        views.configurar_horario,
        name='configurar_horario'
    ),
    path(
        'configurar-horario/dia/crear/',
        views.crear_dia_horario,
        name='crear_dia_horario'
    ),

    path(
        'configurar-horario/hora/crear/',
        views.crear_hora_horario,
        name='crear_hora_horario'
    ),
    path(
        'cronometro/',
        views.cronometro_lucha,
        name='cronometro_lucha'
    ),
]
