from django.urls import path
from . import views


urlpatterns = [

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
