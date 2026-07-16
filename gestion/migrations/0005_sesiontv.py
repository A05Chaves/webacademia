import django.db.models.deletion
import gestion.models
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('gestion', '0004_configuracionhome_video_promo_archivo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SesionTV',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('codigo', models.CharField(max_length=6, unique=True)),
                ('estado', models.JSONField(default=gestion.models.estado_tv_inicial)),
                ('activa', models.BooleanField(default=True)),
                ('expira_en', models.DateTimeField()),
                ('creada', models.DateTimeField(auto_now_add=True)),
                ('actualizada', models.DateTimeField(auto_now=True)),
                ('propietario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sesiones_tv', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-creada']},
        ),
    ]
