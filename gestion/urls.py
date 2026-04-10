from django.urls import path
from . import views

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
]