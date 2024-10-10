from django.db import models


class UserType(models.IntegerChoices):
    ADMIN = 1, 'Администратор',
    EMPLOYEE = 2, 'Сотрудник',
    MANAGER = 3, 'Руководитель',
    DIRECTOR = 4, 'Директор'


class UserStatus(models.IntegerChoices):
    NA = 1, 'Статус не установлен',
    BEGIN = 2, 'Приход на работу',
    BEGIN_LANCH = 3, 'Уход на обед',
    END_LANCH = 4, 'Приход с обеда',
    END = 5, 'Уход с работы'


class Department(models.Model):
    name = models.CharField(max_length=1024)
    begin = models.TimeField('Начало рабочего времени')
    begin_lanch = models.TimeField('Начало обеда')
    end_lanch = models.TimeField('Конец обеда')
    end = models.TimeField('Конец дня')


class TgUser(models.Model):
    is_new = models.BooleanField(default=False)
    tg_id = models.IntegerField()
    username = models.CharField(max_length=255)
    user_type = models.IntegerField(choices=UserType)
    status = models.IntegerField(choices=UserStatus, default=UserStatus.NA)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)


class ActionLog(models.Model):
    user = models.ForeignKey(TgUser)
    created = models.DateTimeField(auto_now_add=True)
    status_before = models.IntegerField(choices=UserStatus, default=UserStatus.NA)
    status_new = models.IntegerField(choices=UserStatus, default=UserStatus.NA)
