from django.urls import path

from alumnos import admin
from config.urls import home_redirect
from . import views
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path, include
from django.contrib.auth import views as auth_views

app_name = 'gestion'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
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
    path('horario/<int:clase_id>/confirmar/',
         views.confirmar_asistencia, name='confirmar_asistencia'),
    path('horario/crear/', views.crear_clase, name='crear_clase'),
    path('horario/<int:clase_id>/editar/',
         views.editar_clase, name='editar_clase'),

    path('horario/confirmar-kiosko/', views.confirmar_asistencia_kiosko,
         name='confirmar_asistencia_kiosko'),
    path(
        'horario/<int:clase_id>/asistentes/',
        views.asistentes_clase,
        name='asistentes_clase'
    ),
]
