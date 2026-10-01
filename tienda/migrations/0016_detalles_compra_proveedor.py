import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def crear_detalles_compras_existentes(apps, schema_editor):
    Compra = apps.get_model('tienda', 'CompraProveedorTienda')
    Detalle = apps.get_model('tienda', 'DetalleCompraProveedorTienda')
    detalles = [
        Detalle(
            compra_id=compra.pk,
            producto_id=compra.producto_id,
            cantidad=compra.cantidad,
            costo_unitario=compra.costo_unitario,
            total=compra.total,
        )
        for compra in Compra.objects.all().iterator()
    ]
    Detalle.objects.bulk_create(detalles)


def eliminar_detalles_compras(apps, schema_editor):
    apps.get_model('tienda', 'DetalleCompraProveedorTienda').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tienda', '0015_productotienda_disponible_sobre_pedido_pedidotienda_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DetalleCompraProveedorTienda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('costo_unitario', models.DecimalField(decimal_places=2, max_digits=14)),
                ('total', models.DecimalField(decimal_places=2, max_digits=14)),
                ('compra', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='tienda.compraproveedortienda')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='detalles_compra_proveedor', to='tienda.productotienda')),
            ],
            options={
                'verbose_name': 'Detalle de compra a proveedor',
                'verbose_name_plural': 'Detalles de compras a proveedores',
                'ordering': ['id'],
            },
        ),
        migrations.RunPython(
            crear_detalles_compras_existentes,
            eliminar_detalles_compras,
        ),
    ]
