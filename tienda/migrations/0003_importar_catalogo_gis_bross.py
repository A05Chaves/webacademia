from django.db import migrations


def importar_catalogo(apps, schema_editor):
    Categoria = apps.get_model('tienda', 'CategoriaProducto')
    Subcategoria = apps.get_model('tienda', 'SubcategoriaProducto')
    Producto = apps.get_model('tienda', 'ProductoTienda')

    categoria, _ = Categoria.objects.get_or_create(
        codigo='100', defaults={'nombre': 'Uniformes', 'activa': True}
    )
    subcategoria, _ = Subcategoria.objects.get_or_create(
        codigo='101',
        defaults={'categoria': categoria, 'nombre': 'Gi', 'activa': True},
    )
    variantes = []
    for genero, tallas in (
        ('HOMBRE', ('A0', 'A1', 'A2', 'A3', 'A4')),
        ('MUJER', ('F0', 'F1', 'F2', 'F3', 'F4')),
    ):
        for color in ('Blanco', 'Negro', 'Azul'):
            for talla in tallas:
                variantes.append((genero, color, talla))

    for indice, (genero, color, talla) in enumerate(variantes, start=1):
        consecutivo = f'{indice:03d}'
        Producto.objects.get_or_create(
            referencia=f'SKU-100-101-001-{consecutivo}',
            defaults={
                'categoria': categoria,
                'subcategoria': subcategoria,
                'codigo_producto': '100-101-001',
                'codigo_barras': f'100-101-001-{consecutivo}',
                'nombre': 'Gi Bross Fight Sport',
                'marca': 'Bross Fight Sport',
                'disciplina': 'BJJ',
                'publico': 'ADULTO',
                'genero': genero,
                'color': color,
                'talla': talla,
                'unidad': 'Unidad',
                'moneda': 'COP',
                'costo_unitario': 0,
                'precio_venta': 0,
                'stock': 0,
                'stock_minimo': 0,
                'activo': True,
            },
        )


def retirar_catalogo(apps, schema_editor):
    Producto = apps.get_model('tienda', 'ProductoTienda')
    Producto.objects.filter(referencia__startswith='SKU-100-101-001-').delete()


class Migration(migrations.Migration):
    dependencies = [('tienda', '0002_categoriaproducto_clientetienda_detalleventatienda_and_more')]
    operations = [migrations.RunPython(importar_catalogo, retirar_catalogo)]
