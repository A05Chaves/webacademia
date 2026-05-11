from django.urls import path
from . import views

app_name = 'cortesias'

urlpatterns = [

    path(
        'registrar/<int:clase_id>/',
        views.registrar_cortesia,
        name='registrar_cortesia'
    ),

]
