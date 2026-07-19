from django.db import migrations


def crear_cuotas(apps, schema_editor):
    Venta = apps.get_model('tienda', 'VentaTienda')
    Cuota = apps.get_model('tienda', 'CuotaVentaTienda')
    for venta in Venta.objects.filter(modalidad='CREDITO'):
        if Cuota.objects.filter(venta=venta).exists():
            continue
        saldo = venta.saldo_pendiente
        estado = 'PAGADA' if saldo == 0 else ('PARCIAL' if saldo < venta.total else 'PENDIENTE')
        Cuota.objects.create(
            venta=venta,
            numero=1,
            fecha_vencimiento=venta.fecha_vencimiento or venta.fecha.date(),
            valor=venta.total,
            saldo=saldo,
            estado=estado,
        )


class Migration(migrations.Migration):
    dependencies = [('tienda', '0004_ventatienda_numero_cuotas_cuotaventatienda_and_more')]
    operations = [migrations.RunPython(crear_cuotas, migrations.RunPython.noop)]
