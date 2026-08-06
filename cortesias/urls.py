from django.urls import path
from . import views

app_name = 'cortesias'

urlpatterns = [

    path(
        'registrar/',
        views.registrar_cortesia,
        name='iniciar_cortesia'
    ),

    path(
        'registrar/<int:clase_id>/',
        views.registrar_cortesia,
        name='registrar_cortesia'
    ),
    path(
        'seleccionar/<int:cortesia_id>/<int:clase_id>/',
        views.seleccionar_clase_cortesia,
        name='seleccionar_clase_cortesia'
    ),
    path(
        'lista/',
        views.lista_cortesias,
        name='lista_cortesias'
    ),
    path(
        '<int:cortesia_id>/contactado/',
        views.cambiar_contactado,
        name='cambiar_contactado'
    ),
    path(
        '<int:cortesia_id>/asistencia/',
        views.cambiar_asistencia,
        name='cambiar_asistencia'
    ),

]
