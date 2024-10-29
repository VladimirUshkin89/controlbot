# Generated by Django 5.1.2 on 2024-10-15 11:42

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=1024)),
                ('begin', models.TimeField(verbose_name='Начало рабочего времени')),
                ('begin_lanch', models.TimeField(verbose_name='Начало обеда')),
                ('end_lanch', models.TimeField(verbose_name='Конец обеда')),
                ('end', models.TimeField(verbose_name='Конец дня')),
            ],
        ),
        migrations.CreateModel(
            name='TgUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_new', models.BooleanField(default=False)),
                ('tg_id', models.IntegerField()),
                ('username', models.CharField(max_length=255)),
                ('first_name', models.CharField(max_length=255)),
                ('last_name', models.CharField(max_length=255)),
                ('user_type', models.IntegerField(choices=[(1, 'Администратор'), (2, 'Сотрудник'), (3, 'Руководитель'), (4, 'Директор')])),
                ('status', models.IntegerField(choices=[(1, 'Статус не установлен'), (2, 'Приход на работу'), (3, 'Уход на обед'), (4, 'Приход с обеда'), (5, 'Уход с работы')], default=1)),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bot.department')),
            ],
        ),
        migrations.CreateModel(
            name='ActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('status_before', models.IntegerField(choices=[(1, 'Статус не установлен'), (2, 'Приход на работу'), (3, 'Уход на обед'), (4, 'Приход с обеда'), (5, 'Уход с работы')], default=1)),
                ('status_new', models.IntegerField(choices=[(1, 'Статус не установлен'), (2, 'Приход на работу'), (3, 'Уход на обед'), (4, 'Приход с обеда'), (5, 'Уход с работы')], default=1)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bot.tguser')),
            ],
        ),
    ]
