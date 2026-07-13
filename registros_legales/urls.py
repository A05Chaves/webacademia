from django.urls import path
from . import views


urlpatterns = [

    path(
        'registro/validar-datos/',
        views.validar_datos_registro,
        name='validar_datos_registro'
    ),

    path(
        'registro/',
        views.registro_publico,
        name='registro_publico'
    ),

    path(
        'registro/exitoso/',
        views.registro_exitoso,
        name='registro_exitoso'
    ),

]
