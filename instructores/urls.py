from django.urls import path

from . import views


app_name = 'instructores'

urlpatterns = [
    path('registro-profesor/', views.registro_profesor, name='registro_profesor'),
    path(
        'registro-profesor/exitoso/',
        views.registro_profesor_exitoso,
        name='registro_profesor_exitoso',
    ),
]
