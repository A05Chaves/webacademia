from django.db import migrations


def unificar_academia_galeras(apps, schema_editor):
    Academia = apps.get_model('pagos', 'AcademiaCompetidora')
    Inscripcion = apps.get_model('pagos', 'InscripcionEvento')

    principal = Academia.objects.filter(nombre__iexact='Galeras BJJ').first()
    if principal is None:
        principal = Academia.objects.create(nombre='Galeras BJJ', activa=True)

    alias = list(
        Academia.objects.filter(nombre__iexact='GALERAS').exclude(pk=principal.pk)
    )
    if not principal.logo:
        origen_logo = next((academia for academia in alias if academia.logo), None)
        if origen_logo:
            principal.logo = origen_logo.logo
    principal.nombre = 'Galeras BJJ'
    principal.activa = True
    principal.save(update_fields=['nombre', 'logo', 'activa', 'actualizada'])

    for academia in alias:
        Inscripcion.objects.filter(academia_equipo_id=academia.id).update(
            academia_equipo_id=principal.id
        )
        academia.activa = False
        academia.save(update_fields=['activa', 'actualizada'])


class Migration(migrations.Migration):
    dependencies = [
        ('pagos', '0012_llavecategoriaevento'),
    ]

    operations = [
        migrations.RunPython(
            unificar_academia_galeras,
            migrations.RunPython.noop,
        ),
    ]
