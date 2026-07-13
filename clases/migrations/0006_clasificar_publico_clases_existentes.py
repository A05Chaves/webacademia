from django.db import migrations
from django.db.models import Q


def clasificar_clases_existentes(apps, schema_editor):
    ClaseProgramada = apps.get_model('clases', 'ClaseProgramada')
    clases_infantiles = (
        Q(titulo__icontains='NIÑ')
        | Q(titulo__icontains='NIN')
        | Q(titulo__icontains='INFANT')
        | Q(titulo__icontains='KID')
    )

    ClaseProgramada.objects.update(publico_objetivo='ADULTO')
    ClaseProgramada.objects.filter(clases_infantiles).update(
        publico_objetivo='MENOR'
    )


def revertir_clasificacion(apps, schema_editor):
    ClaseProgramada = apps.get_model('clases', 'ClaseProgramada')
    ClaseProgramada.objects.update(publico_objetivo='TODOS')


class Migration(migrations.Migration):
    dependencies = [
        ('clases', '0005_claseprogramada_publico_objetivo'),
    ]

    operations = [
        migrations.RunPython(
            clasificar_clases_existentes,
            revertir_clasificacion,
        ),
    ]
