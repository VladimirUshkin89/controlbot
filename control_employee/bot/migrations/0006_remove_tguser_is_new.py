# Generated by Django 5.1.2 on 2024-10-18 07:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0005_alter_tguser_username'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tguser',
            name='is_new',
        ),
    ]
