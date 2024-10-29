from django.db import models


class UserType(models.IntegerChoices):
    ADMIN = 1, 'Администратор',
    EMPLOYEE = 2, 'Сотрудник',
    MANAGER = 3, 'Руководитель',
    DIRECTOR = 4, 'Директор'
    NEW = 5, 'Новый сотрудник'
    DECLINED = 6, 'Отказано в регистрации'


class UserStatus(models.IntegerChoices):
    NA = 1, 'Статус не установлен',
    BEGIN = 2, 'Приход на работу',
    BEGIN_LANCH = 3, 'Уход на обед',
    END_LANCH = 4, 'Приход с обеда',
    END = 5, 'Уход с работы'


class Department(models.Model):
    name = models.CharField(max_length=1024)
    begin = models.TimeField('Начало рабочего времени', null=True, blank=True)
    begin_lanch = models.TimeField('Начало обеда', null=True, blank=True)
    end_lanch = models.TimeField('Конец обеда', null=True, blank=True)
    end = models.TimeField('Конец дня', null=True, blank=True)


class TgUser(models.Model):
    tg_id = models.BigIntegerField()
    username = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    user_type = models.IntegerField(choices=UserType, default=UserType.NEW.value)
    status = models.IntegerField(choices=UserStatus, default=UserStatus.NA)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True)

    @property
    def name(self):
        result = ''
        last_name = self.last_name or ''
        first_name = self.first_name or ''
        if any((last_name, first_name)):
            result = ' '.join((last_name, first_name))
        elif self.username:
            result = self.username
        return result


class ActionLog(models.Model):
    user = models.ForeignKey(TgUser, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    status_before = models.IntegerField(choices=UserStatus, default=UserStatus.NA)
    status_new = models.IntegerField(choices=UserStatus, default=UserStatus.NA)
