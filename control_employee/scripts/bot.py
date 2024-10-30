import asyncio
import datetime
import typing
from enum import Enum

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.handlers import CallbackQueryHandler, MessageHandler
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, Message, ReplyKeyboardRemove, BotCommand)
from asgiref.sync import sync_to_async
from bot.models import ActionLog, Department, TgUser, UserStatus, UserType
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone
from geopy.distance import geodesic

form_router = Router()

commands = [
    BotCommand(command='menu', description='Главное меню')
]

bot = Bot(token=settings.TOKEN_BOT, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
bot.set_my_commands(commands)
dp = Dispatcher()


class DepartmentStateGroup(StatesGroup):
    old_name = State()
    new_name = State()
    create = State()


class WorkTimeStateGroup(StatesGroup):
    nothing = State()
    set_begin = State()
    set_begin_lanch = State()
    set_end_lanch = State()
    set_end = State()


class TransferAdmin(StatesGroup):
    add_admin_state = State()


class DepartmentAction(str, Enum):
    list = 'list'
    rename = 'rename'
    delete = 'delete'
    employees = 'employees'
    set_work_time = 'set_work_time'
    create = 'create'
    back = 'back'


class DepartmentCallback(CallbackData, prefix="department"):
    action: DepartmentAction
    department_id: typing.Optional[int] = None


class ReportAction(str, Enum):
    today = 'today'
    yesterday = 'yesterday'
    week = 'week'
    month = 'month'


class ReportCallback(CallbackData, prefix='report'):
    action: ReportAction
    user_id: typing.Optional[int] = None


class EmployeeAction(str, Enum):
    update_status = 'update_status'
    confirm_yes = 'confirm_yes'
    confirm_no = 'confirm_no'


class EmployeeCallback(CallbackData, prefix='employee'):
    action: EmployeeAction
    user_id: typing.Optional[int] = None
    prev_status: UserStatus
    new_status: UserStatus


class UserAction(str, Enum):
    list_new = 'list_new'
    list_registered = 'list_registered'

    apply_employee = 'apply_employee'
    apply_manager = 'apply_manager'
    apply_director = 'apply_director'
    decline = 'decline'

    delete = 'delete'

    registered_users = 'registered_users'

    list_directors = 'list_directors'
    list_managers = 'list_managers'
    list_employees = 'list_employees'

    change_department = 'change_department'

    back = 'back'
    registered_back = 'registered_back'

    no_new_users = 'no_new_users'

    set_new_status = 'set_new_status'

    add_admin = 'add_admin'

    set_new_department = 'set_new_department'


class UserCallback(CallbackData, prefix='user'):
    action: UserAction
    user_id: typing.Optional[int] = None
    department_id: typing.Optional[int] = None


class WorkTimeAction(str, Enum):
    get_current = 'get_current'
    set_begin = 'set_begin'
    set_begin_lanch = 'set_begin_lanch'
    set_end_lanch = 'set_end_lanch'
    set_end = 'set_end'


class WorkTimeCallback(CallbackData, prefix='work_time'):
    action: WorkTimeAction
    department_id: typing.Optional[int] = None


admin_menu_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(
            text='Новые пользователи',
            callback_data=UserCallback(action=UserAction.list_new).pack()
        )],
        [InlineKeyboardButton(
            text='Зарегистрированные пользователи',
            callback_data=UserCallback(action=UserAction.registered_users).pack()
        )],
        [InlineKeyboardButton(
            text='Список подразделений',
            callback_data=DepartmentCallback(action=DepartmentAction.list).pack()
        )],
        [InlineKeyboardButton(
            text='Создать новое подразделение',
            callback_data=DepartmentCallback(action=DepartmentAction.create).pack()
        )],
        [InlineKeyboardButton(
            text='Добавить администратора',
            callback_data=UserCallback(action=UserAction.add_admin).pack()
        )],
    ]
)

registered_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Директора', callback_data=UserCallback(action=UserAction.list_directors).pack())],
    [InlineKeyboardButton(text='Руководители', callback_data=UserCallback(action=UserAction.list_managers).pack())],
    [InlineKeyboardButton(text='Сотрудники', callback_data=UserCallback(action=UserAction.list_employees).pack())],
    [InlineKeyboardButton(text='Назад', callback_data=UserCallback(action=UserAction.back).pack())],
])

director_menu_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(
            text='Список подразделений',
            callback_data=DepartmentCallback(action=DepartmentAction.list).pack()
        )]
    ]
)

user_location_kb = ReplyKeyboardRemove(
    keyboard=[[KeyboardButton(text='Отправить геолокацию', request_location=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

user_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(
            text='Установить статус',
            callback_data=UserCallback(action=UserAction.set_new_status).pack()
        )]
    ]
)

manager_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(
            text='Список подразделений', callback_data=DepartmentCallback(action=DepartmentAction.list).pack()
        )]
    ]
)


INTERFACE = {
    UserType.ADMIN.value: ('Меню администратора', admin_menu_kb),
    UserType.EMPLOYEE.value: ('', user_kb),
    UserType.MANAGER.value: ('Вывести список сотрудников', manager_kb),
    UserType.DIRECTOR.value: ('Список подразделений', director_menu_kb),
}


@sync_to_async
def get_user(tg_id):
    return TgUser.objects.filter(tg_id=tg_id).first()


@sync_to_async
def get_or_create_user(tg_user):
    user, created = TgUser.objects.get_or_create(tg_id=tg_user.id)
    if created:
        if tg_user.username:
            user.username = tg_user.username
        if tg_user.first_name:
            user.first_name = tg_user.first_name
        if tg_user.last_name:
            user.last_name = tg_user.last_name
        user.save()
    return user


@sync_to_async
def get_user_department(user_id):
    return Department.objects.filter(tguser__id=user_id).first()


async def clear_messages(bot, chat_id, message_id, only_previous: bool = True):
    message_ids = []
    if only_previous:
        message_ids = list(range(message_id, message_id - 100, -1))
    else:
        message_ids = list(range(message_id + 50, message_id - 50, -1))
    try:
        await bot.delete_messages(
            chat_id,
            message_ids
        )
    except TelegramBadRequest:
        pass


@form_router.callback_query(UserCallback.filter(F.action.in_(UserAction)))
class UserHandler(CallbackQueryHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {
            UserAction.apply_employee: self.apply_employee,
            UserAction.apply_manager: self.apply_manager,
            UserAction.apply_director: self.apply_director,
            UserAction.decline: self.decline,
            UserAction.back: self.back,
            UserAction.list_directors: self.list_directors,
            UserAction.list_managers: self.list_managers,
            UserAction.list_employees: self.list_employees,
            UserAction.registered_back: self.registered_back,
            UserAction.no_new_users: self.no_new_users
        }
        self.registered_users_back_button = InlineKeyboardButton(
            text='Назад',
            callback_data=UserCallback(action=UserAction.registered_users).pack()
        )
        self.no_new_users_back_button = InlineKeyboardButton(
            text='Назад',
            callback_data=UserCallback(action=UserAction.no_new_users).pack()
        )

    @sync_to_async
    def get_new_users(self):
        return list(TgUser.objects.filter(user_type=UserType.NEW.value).all())

    @sync_to_async
    def delete_user(self, user_id):
        TgUser.objects.filter(id=user_id).delete()

    async def set_user_type(self, user_id, user_type: UserType):
        @sync_to_async
        def set_type(user_id, user_type: UserType):
            return TgUser.objects.filter(id=user_id).update(user_type=user_type.value)
        await set_type(user_id, user_type)

    async def apply_employee(self, user_id):
        await self.set_user_type(user_id, UserType.EMPLOYEE)

    async def apply_manager(self, user_id):
        await self.set_user_type(user_id, UserType.MANAGER)

    async def apply_director(self, user_id):
        await self.set_user_type(user_id, UserType.DIRECTOR)

    async def decline(self, user_id):
        await self.set_user_type(user_id, UserType.DECLINED)

    @sync_to_async
    def get_users_by_type(self, user_type):
        return list(TgUser.objects.filter(user_type=user_type.value).all())

    async def list_directors(self):
        directors = await self.get_users_by_type(UserType.DIRECTOR)
        if directors:
            for director in directors:
                director_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Удалить пользователя',
                        callback_data=UserCallback(action=UserAction.delete, user_id=director.id).pack()
                    )],
                    [self.registered_users_back_button],
                ])
                await self.message.answer(f'{director.name}', reply_markup=director_kb)
        else:
            director_kb = InlineKeyboardMarkup(
                inline_keyboard=[[self.registered_users_back_button]]
            )
            await self.message.answer('Отсутствуют директоры', reply_markup=director_kb)

    async def list_managers(self):
        managers = await self.get_users_by_type(UserType.MANAGER)
        if managers:
            for manager in managers:
                manager_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Удалить пользователя',
                        callback_data=UserCallback(action=UserAction.delete, user_id=manager.id).pack()
                    )],
                    [InlineKeyboardButton(
                        text='Изменить подразделение',
                        callback_data=UserCallback(action=UserAction.change_department, user_id=manager.id).pack()
                    )],
                    [self.registered_users_back_button],
                ])
                await self.message.answer(f'{manager.name}', reply_markup=manager_kb)
        else:
            manager_kb = InlineKeyboardMarkup(
                inline_keyboard=[[self.registered_users_back_button]]
            )
            await self.message.answer('Отсутствуют руководители', reply_markup=manager_kb)

    async def list_employees(self):
        employees = await self.get_users_by_type(UserType.EMPLOYEE)
        if employees:
            for employee in employees:
                manager_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Удалить пользователя',
                        callback_data=UserCallback(action=UserAction.delete, user_id=employee.id).pack()
                    )],
                    [InlineKeyboardButton(
                        text='Изменить подразделение',
                        callback_data=UserCallback(action=UserAction.change_department, user_id=employee.id).pack()
                    )],
                    [self.registered_users_back_button],
                ])
                msg = f'{employee.name}'
                await self.message.answer(msg, reply_markup=manager_kb)
        else:
            manager_kb = InlineKeyboardMarkup(
                inline_keyboard=[[self.registered_users_back_button]]
            )
            await self.message.answer('Отсутствуют сотрудники', reply_markup=manager_kb)

    async def back(self):
        await self.message.answer('Меню администратора', reply_markup=admin_menu_kb)

    async def registered_back(self):
        await self.message.answer('Зарегистрированные пользователи', reply_markup=registered_menu_kb)

    async def no_new_users(self):
        await self.message.answer('Меню администратора', reply_markup=admin_menu_kb)

    @sync_to_async
    def _list_departments(self):
        return list(Department.objects.all())

    @sync_to_async
    def get_department(self, department_id):
        return Department.objects.filter(id=department_id).first()

    @sync_to_async
    def get_user(self, user_id):
        return TgUser.objects.filter(id=user_id).first()

    @sync_to_async
    def update_user_department(self, user_id, department_id):
        return TgUser.objects.filter(id=user_id).update(department_id=department_id)

    async def handle(self) -> typing.Any:
        callback_data = UserCallback.unpack(self.callback_data)
        if callback_data.action is UserAction.list_new:
            new_users = await self.get_new_users()
            if new_users:
                for new_user in new_users:
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text='Принять как сотрудника',
                            callback_data=UserCallback(action=UserAction.apply_employee, user_id=new_user.id).pack()
                        )],
                        [InlineKeyboardButton(
                            text='Принять как руководителя',
                            callback_data=UserCallback(action=UserAction.apply_manager, user_id=new_user.id).pack()
                        )],
                        [InlineKeyboardButton(
                            text='Принять как директора',
                            callback_data=UserCallback(action=UserAction.apply_director, user_id=new_user.id).pack()
                        )],
                        [InlineKeyboardButton(
                            text='Отказать в регистрации',
                            callback_data=UserCallback(action=UserAction.decline, user_id=new_user.id).pack()
                        )],
                        [self.registered_users_back_button],
                    ])
                    await self.message.answer(
                        f'{new_user.name}',
                        reply_markup=kb
                    )
            else:
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[[self.no_new_users_back_button]]
                )
                await self.message.answer('Отсутствуют новые пользователи', reply_markup=kb)
        elif callback_data.action is UserAction.delete:
            user = await get_or_create_user(self.message.from_user)
            if not user.id == callback_data.user_id:
                await self.delete_user(callback_data.user_id)
                await self.message.answer('Меню администратора', reply_markup=admin_menu_kb)
            else:
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[[self.no_new_users_back_button]]
                )
                await self.message.answer('Нельзя удалить себя', reply_markup=kb)
        elif callback_data.action in (
            UserAction.apply_employee,
            UserAction.apply_manager,
            UserAction.apply_director,
            UserAction.decline,
        ):
            action = self.actions.get(callback_data.action)
            await action(callback_data.user_id)
            reply_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Назад',
                        callback_data=UserCallback(action=UserAction.list_new).pack()
                    )]
                ]
            )
            await self.message.answer('Пользователь принят', reply_markup=reply_kb)
        elif callback_data.action is UserAction.registered_users:
            await self.message.answer('Зарегистрированные пользователи', reply_markup=registered_menu_kb)
        elif callback_data.action in (
            UserAction.list_directors,
            UserAction.list_managers,
            UserAction.list_employees,
            UserAction.no_new_users,
        ):
            action = self.actions.get(callback_data.action)
            await action()
        elif callback_data.action is UserAction.change_department:
            change_department_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=dp.name,
                            callback_data=UserCallback(
                                action=UserAction.set_new_department,
                                department_id=dp.id,
                                user_id=callback_data.user_id
                            ).pack()
                        )
                    ]
                    for dp in await self._list_departments()
                ]
            )
            await self.message.answer('Выберите подразделение', reply_markup=change_department_kb)
        elif callback_data.action is UserAction.set_new_department:
            user = await self.get_user(callback_data.user_id)
            result = await self.update_user_department(callback_data.user_id, callback_data.department_id)
            back_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Назад',
                        callback_data=UserCallback(action=UserAction.list_employees).pack()
                    )]
                ]
            )
            if result:
                await self.message.answer(f'У пользователя {user.name} изменено подразделение', reply_markup=back_kb)
            else:
                await self.message.answer(
                    f'Не удалось изменить подразделение у пользователя {user.name}',
                    reply_markup=back_kb
                )
        elif callback_data.action is UserAction.back:
            await self.back()
        elif callback_data.action is UserAction.set_new_status:
            await self.message.answer('Отправьте геолокацию', reply_markup=user_location_kb)
        elif callback_data.action is UserAction.add_admin:
            await self.data['state'].set_state(TransferAdmin.add_admin_state)
            await self.message.answer('Укажите username нового админа')
        await clear_messages(self.bot, self.message.chat.id, self.message.message_id)
        return await super().handle()


@form_router.callback_query(DepartmentCallback.filter(F.action.in_(DepartmentAction)))
class DepartmentsUser(CallbackQueryHandler):

    @sync_to_async
    def get_list_of_departments(self, user):
        user_type = UserType(user.user_type)
        if user_type in (UserType.ADMIN, UserType.DIRECTOR):
            qs = Department.objects.all()
        elif user_type is UserType.MANAGER:
            qs = Department.objects.filter(id=user.department_id).all()
        return list(qs)

    @sync_to_async
    def get_employees_of_department(self, department_id):
        return list(TgUser.objects.filter(department_id=department_id).all())

    @sync_to_async
    def get_department(self, department_id):
        return Department.objects.filter(id=department_id).first()

    @sync_to_async
    def _delete_department(self, department_id):
        return Department.objects.filter(id=department_id).delete()

    async def send_departments_list(self):
        user = await get_or_create_user(self.from_user)
        user_type = UserType(user.user_type)
        departments = await self.get_list_of_departments(user)
        admin_department_back_button = InlineKeyboardButton(
            text='Назад',
            callback_data=DepartmentCallback(action=DepartmentAction.back).pack()
        )
        department_back_button = InlineKeyboardButton(
            text='Назад',
            callback_data=DepartmentCallback(action=DepartmentAction.list).pack()
        )
        if departments:
            for department in departments:
                department_kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text='Сотрудники',
                            callback_data=DepartmentCallback(
                                action=DepartmentAction.employees,
                                department_id=department.id
                            ).pack()
                        )],
                    ]
                )
                if user_type is UserType.ADMIN:
                    department_kb.inline_keyboard.append(
                        [InlineKeyboardButton(
                            text='Установить рабочее время',
                            callback_data=DepartmentCallback(
                                action=DepartmentAction.set_work_time,
                                department_id=department.id
                            ).pack()
                        )]
                    )
                    department_kb.inline_keyboard.append(
                        [InlineKeyboardButton(
                            text='Переименовать подразделение',
                            callback_data=DepartmentCallback(
                                action=DepartmentAction.rename,
                                department_id=department.id
                            ).pack()
                        )]
                    )
                    department_kb.inline_keyboard.append(
                        [InlineKeyboardButton(
                            text='Удалить подразделение',
                            callback_data=DepartmentCallback(
                                action=DepartmentAction.delete,
                                department_id=department.id
                            ).pack()
                        )]
                    )
                    department_kb.inline_keyboard.append(
                        [admin_department_back_button]
                    )
                elif user_type is UserType.DIRECTOR:
                    department_kb.inline_keyboard.append(
                        [department_back_button]
                    )
                elif user_type is UserType.MANAGER:
                    department_kb.inline_keyboard.append(
                        [InlineKeyboardButton(
                            text='Установить рабочее время',
                            callback_data=DepartmentCallback(
                                action=DepartmentAction.set_work_time,
                                department_id=department.id
                            ).pack()
                        )]
                    )
                    department_kb.inline_keyboard.append(
                        [department_back_button]
                    )
                await self.message.answer(f'{department.name}', reply_markup=department_kb)
        else:
            if user_type is UserType.ADMIN:
                department_kb = InlineKeyboardMarkup(
                    inline_keyboard=[[admin_department_back_button]]
                )
            elif user_type in (UserType.DIRECTOR, UserType.MANAGER):
                department_kb = InlineKeyboardMarkup(
                    inline_keyboard=[[department_back_button]]
                )
            await self.message.answer('Отсутствуют подразделения', reply_markup=department_kb)

    async def send_employees_of_department(self, department_id):
        department_employees = await self.get_employees_of_department(department_id)
        department_back_button = InlineKeyboardButton(
            text='Назад',
            callback_data=DepartmentCallback(action=DepartmentAction.list).pack()
        )
        if department_employees:
            for employee in department_employees:
                employee_kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text='Отчет за сегодня',
                            callback_data=ReportCallback(action=ReportAction.today, user_id=employee.id).pack()
                        )],
                        [InlineKeyboardButton(
                            text='Отчет за вчера',
                            callback_data=ReportCallback(action=ReportAction.yesterday, user_id=employee.id).pack()
                        )],
                        [InlineKeyboardButton(
                            text='Отчет за 7 дней',
                            callback_data=ReportCallback(action=ReportAction.week, user_id=employee.id).pack()
                        )],
                        [InlineKeyboardButton(
                            text='Отчет за месяц',
                            callback_data=ReportCallback(action=ReportAction.month, user_id=employee.id).pack()
                        )],
                        [department_back_button],
                    ]
                )
                msg = f'{employee.name} {employee.id}'
                await self.message.answer(msg, reply_markup=employee_kb)
        else:
            employee_kb = InlineKeyboardMarkup(
                inline_keyboard=[[department_back_button]]
            )
            await self.message.answer('Отсутствуют сотрудники', reply_markup=employee_kb)

    async def set_work_time(self, department_id):
        department = await self.get_department(department_id)
        work_time_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text='Текущее время',
                    callback_data=WorkTimeCallback(
                        action=WorkTimeAction.get_current,
                        department_id=department.id
                    ).pack()
                )],
                [InlineKeyboardButton(
                    text='Начало рабочего дня (Установка времени)',
                    callback_data=WorkTimeCallback(
                        action=WorkTimeAction.set_begin,
                        department_id=department.id
                    ).pack()
                )],
                [InlineKeyboardButton(
                    text='Начало обеда (Установка времени)',
                    callback_data=WorkTimeCallback(
                        action=WorkTimeAction.set_begin_lanch,
                        department_id=department.id
                    ).pack()
                )],
                [InlineKeyboardButton(
                    text='Конец обеда (Установка времени)',
                    callback_data=WorkTimeCallback(
                        action=WorkTimeAction.set_end_lanch,
                        department_id=department.id
                    ).pack()
                )],
                [InlineKeyboardButton(
                    text='Конец рабочего дня (Установка времени)',
                    callback_data=WorkTimeCallback(
                        action=WorkTimeAction.set_end,
                        department_id=department.id
                    ).pack()
                )],
                [InlineKeyboardButton(
                    text='Назад',
                    callback_data=DepartmentCallback(
                        action=DepartmentAction.list,
                        department_id=department.id
                    ).pack()
                )],
            ]
        )
        await self.message.answer(f'{department.name}', reply_markup=work_time_kb)

    async def delete_department(self, department_id):
        await self._delete_department(department_id)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text='Назад',
                    callback_data=DepartmentCallback(action=DepartmentAction.list).pack()
                )],
            ]
        )
        await self.message.answer('Удалено подразделение', reply_markup=kb)

    async def rename_department(self, department_id):
        department = await self.get_department(department_id)
        await self.message.answer('Введите новое название подразделения')
        await self.data['state'].set_state(DepartmentStateGroup.old_name)
        await self.data['state'].update_data(old_name=department.name)
        await self.data['state'].set_state(DepartmentStateGroup.new_name)

    async def create_new_department(self):
        await self.message.answer('Введите название нового подразделения')
        await self.data['state'].set_state(DepartmentStateGroup.create)

    async def back(self):
        await self.message.answer('Меню администратора', reply_markup=admin_menu_kb)

    async def handle(self) -> typing.Any:
        callback_data = DepartmentCallback.unpack(self.callback_data)
        if callback_data.action == DepartmentAction.list:
            await self.send_departments_list()
        elif callback_data.action == DepartmentAction.employees:
            await self.send_employees_of_department(callback_data.department_id)
        elif callback_data.action == DepartmentAction.set_work_time:
            await self.set_work_time(callback_data.department_id)
        elif callback_data.action == DepartmentAction.delete:
            await self.delete_department(callback_data.department_id)
        elif callback_data.action == DepartmentAction.rename:
            await self.rename_department(callback_data.department_id)
        elif callback_data.action == DepartmentAction.create:
            await self.create_new_department()
        elif callback_data.action is DepartmentAction.back:
            await self.back()
        await clear_messages(self.bot, self.message.chat.id, self.message.message_id)
        return await super().handle()


@form_router.callback_query(WorkTimeCallback.filter(F.action.in_(WorkTimeAction)))
class WorkTimeHandler(CallbackQueryHandler):
    @sync_to_async
    def get_department(self, department_id):
        return Department.objects.filter(id=department_id).first()

    async def handle(self) -> typing.Any:
        callback_data = WorkTimeCallback.unpack(self.callback_data)
        dp = await self.get_department(callback_data.department_id)
        if callback_data.action == WorkTimeAction.get_current:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Назад',
                        callback_data=DepartmentCallback(
                            action=DepartmentAction.set_work_time,
                            department_id=dp.id
                        ).pack()
                    )],
                ]
            )
            msg = (
                f'Начало рабочего времени: {dp.begin.strftime("%X")}\n'
                f'Начало обеда: {dp.begin_lanch.strftime("%X")}\n'
                f'Конец обеда: {dp.end_lanch.strftime("%X")}\n'
                f'Конец рабочего дня: {dp.end.strftime("%X")}'
            )
            await self.message.answer(msg, reply_markup=kb)
        if callback_data.action == WorkTimeAction.set_begin:
            await self.data['state'].update_data(department_id=dp.id)
            await self.data['state'].set_state(WorkTimeStateGroup.set_begin)
            await self.message.answer('Установите начало рабочего дня в формате чч мм')
        if callback_data.action == WorkTimeAction.set_begin_lanch:
            await self.data['state'].update_data(department_id=dp.id)
            await self.data['state'].set_state(WorkTimeStateGroup.set_begin_lanch)
            await self.message.answer('Установите начало обеда в формате чч мм')
        if callback_data.action == WorkTimeAction.set_end_lanch:
            await self.data['state'].update_data(department_id=dp.id)
            await self.data['state'].set_state(WorkTimeStateGroup.set_end_lanch)
            await self.message.answer('Установите окончание обеда в формате чч мм')
        if callback_data.action == WorkTimeAction.set_end:
            await self.data['state'].update_data(department_id=dp.id)
            await self.data['state'].set_state(WorkTimeStateGroup.set_end)
            await self.message.answer('Установите окончание рабочего дня в формате чч мм')
        await clear_messages(self.bot, self.message.chat.id, self.message.message_id)
        return await super().handle()


@form_router.callback_query(ReportCallback.filter(F.action.in_(ReportAction)))
class ReportHandler(CallbackQueryHandler):
    @sync_to_async
    def get_report_by_dates(self, user_id, from_date, to_date):
        return list(ActionLog.objects.filter(created__date__gte=from_date, created__date__lte=to_date, user_id=user_id))

    @sync_to_async
    def get_user(self, user_id):
        return TgUser.objects.filter(id=user_id).first()

    async def handle(self) -> typing.Any:
        callback_data = ReportCallback.unpack(self.callback_data)
        if callback_data.action is ReportAction.today:
            to_date = timezone.localdate()
            from_date = timezone.localdate()
        elif callback_data.action is ReportAction.yesterday:
            to_date = timezone.localdate() - datetime.timedelta(days=1)
            from_date = timezone.localdate() - datetime.timedelta(days=1)
        elif callback_data.action is ReportAction.week:
            to_date = timezone.localdate()
            from_date = timezone.localdate() - datetime.timedelta(days=7)
        elif callback_data.action is ReportAction.month:
            to_date = timezone.localdate()
            from_date = timezone.localdate() - relativedelta(months=1)
        report = await self.get_report_by_dates(callback_data.user_id, from_date, to_date)
        msg = '\n\n'.join(
            ['\n'.join((timezone.localtime(r.created).strftime('%d.%m.%Y %X'), UserStatus(r.status_new).label)) for r in report]
        )
        department = await get_user_department(callback_data.user_id)
        if not msg.strip():
            msg = 'Отсутствуют данные за указанный промежуток времени'
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text='Назад',
                    callback_data=DepartmentCallback(
                        action=DepartmentAction.employees,
                        department_id=department.id
                    ).pack()
                )]
            ]
        )
        await clear_messages(self.bot, self.message.chat.id, self.message.message_id, only_previous=False)
        await self.message.answer(msg, reply_markup=back_kb)
        return await super().handle()


@form_router.callback_query(EmployeeCallback.filter(F.action.in_(EmployeeAction)))
class UpdateStatusEmployee(CallbackQueryHandler):
    @sync_to_async
    def update_user_status(self, user_id, prev_status: UserStatus, status: UserStatus):
        TgUser.objects.filter(id=user_id).update(status=status)
        action = ActionLog.objects.create(user_id=user_id, status_before=prev_status.value, status_new=status.value)
        return action

    async def handle(self) -> typing.Any:
        callback_data = EmployeeCallback.unpack(self.callback_data)
        if callback_data.action is EmployeeAction.update_status:
            confirm_yes_no_kb = InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text='Да',
                        callback_data=EmployeeCallback(
                            action=EmployeeAction.confirm_yes,
                            user_id=callback_data.user_id,
                            prev_status=callback_data.prev_status,
                            new_status=callback_data.new_status,
                        ).pack()
                    ),
                    InlineKeyboardButton(
                        text='Нет',
                        callback_data=EmployeeCallback(
                            action=EmployeeAction.confirm_no,
                            user_id=callback_data.user_id,
                            prev_status=callback_data.prev_status,
                            new_status=callback_data.new_status,
                        ).pack()
                    ),
                ]]
            )
            await self.message.answer(
                f'Ваш текущий статус - {callback_data.prev_status.label}.\nСменить статус на {callback_data.new_status.label}?',
                reply_markup=confirm_yes_no_kb
            )
        elif callback_data.action is EmployeeAction.confirm_yes:
            action = await self.update_user_status(
                callback_data.user_id, callback_data.prev_status, callback_data.new_status
            )
            user = await get_or_create_user(self.from_user)
            department = await get_user_department(user.id)
            if action:
                action_created = timezone.localtime(action.created)
                msg = None
                new_status = UserStatus(action.status_new)
                if new_status is UserStatus.BEGIN and department and action_created.time() > department.begin:
                    msg = (
                        f'Сотрудник {user.name} {department.name} прибыл на рабочее место '
                        f'{action_created.time().strftime("%X")}'
                    )
                elif (
                    new_status is UserStatus.BEGIN_LANCH
                    and department and not (department.begin_lanch <= action_created.time() <= department.end_lanch)
                ):
                    msg = (
                        f'Сотрудник {user.name} {department.name} ушел на обед '
                        f'{action_created.time().strftime("%X")}'
                    )
                elif new_status is UserStatus.END_LANCH and department and action_created.time() > department.end_lanch:
                    msg = (
                        f'Сотрудник {user.name} {department.name} вернулся с обеда '
                        f'{action_created.time().strftime("%X")}'
                    )
                elif new_status is UserStatus.END and department and action_created.time() < department.end:
                    msg = (
                        f'Сотрудник {user.name} {department.name} ушел с работы до окончания рабочего дня '
                        f'{action_created.time().strftime("%X")}'
                    )
                if msg:
                    try:
                        await self.bot.send_message(settings.WORK_CHAT_ID, msg)
                    except TelegramBadRequest:
                        pass
            interface = INTERFACE.get(UserType.EMPLOYEE)
            menu_name, menu_kb = interface
            if UserType(user.user_type) is UserType.EMPLOYEE:
                user_status = UserStatus(user.status)
                menu_name = f'Текущий статус: {user_status.label}'
            await self.message.answer(menu_name, reply_markup=menu_kb)
        elif callback_data.action is EmployeeAction.confirm_no:
            user = await get_or_create_user(self.from_user)
            interface = INTERFACE.get(UserType.EMPLOYEE)
            menu_name, menu_kb = interface
            if UserType(user.user_type) is UserType.EMPLOYEE:
                user_status = UserStatus(user.status)
                menu_name = f'Текущий статус: {user_status.label}'
            await self.message.answer(menu_name, reply_markup=menu_kb)
        await clear_messages(self.bot, self.message.chat.id, self.message.message_id)
        return await super().handle()


@form_router.message(F.location)
class LocationMessageHandler(MessageHandler):

    async def handle(self) -> typing.Any:
        await self.data['state'].set_state(None)
        if settings.DEBUG:
            distance_m = geodesic(
                (self.event.location.latitude, self.event.location.longitude),
                (self.event.location.latitude, self.event.location.longitude)
            ).m
        else:
            distance_m = geodesic(
                (45.09150498886614, 39.01328350827073),
                (self.event.location.latitude, self.event.location.longitude)
            ).m
        if distance_m > 100:
            msg = (
                'Ваше место положение не совпадает с местом работы.\n'
                'Пожалуйста вернитесь на место работы и попробуйте еще раз.'
            )
            await self.event.answer(msg)
        else:
            user = await get_or_create_user(self.from_user)
            status_flow = {
                UserStatus.NA: (UserStatus.BEGIN,),
                UserStatus.END: (UserStatus.BEGIN,),
                UserStatus.BEGIN: (UserStatus.BEGIN_LANCH, UserStatus.END),
                UserStatus.BEGIN_LANCH: (UserStatus.END_LANCH, UserStatus.END),
                UserStatus.END_LANCH: (UserStatus.END,),
            }
            user_status = UserStatus(user.status)
            c_data = status_flow.get(user_status)
            user_next_status_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=status.label,
                            callback_data=EmployeeCallback(
                                action=EmployeeAction.update_status,
                                user_id=user.id,
                                prev_status=user.status,
                                new_status=status
                            ).pack())
                    ]
                    for status in c_data
                ]
            )
            await self.event.answer('Укажите статус', reply_markup=user_next_status_kb)
            await clear_messages(self.bot, self.event.chat.id, self.event.message_id)
        return await super().handle()


@form_router.message(WorkTimeStateGroup.set_begin)
class WorkTimeBegin(MessageHandler):
    @sync_to_async
    def set_begin(self, department_id, time):
        Department.objects.filter(id=department_id).update(begin=time)

    async def handle(self) -> typing.Any:
        _data = await self.data['state'].get_data()
        _time_text = self.event.text
        await self.data['state'].set_state(None)
        department_id = _data['department_id']
        if ' ' in _time_text:
            while '  ' in _time_text:
                _time_text = _time_text.replace('  ', ' ')
        if ':' in _time_text:
            _time_text = _time_text.replace(':', ' ')
        try:
            begin_time = datetime.datetime.strptime(_time_text, '%H %M')
        except ValueError:
            await self.message.answer('Введите время в формате чч мм')
        else:
            await self.set_begin(department_id, begin_time)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Назад',
                        callback_data=DepartmentCallback(
                            action=DepartmentAction.set_work_time,
                            department_id=department_id
                        ).pack()
                    )],
                ]
            )
            await self.event.answer(f'Установлено время {begin_time.strftime("%H:%M")}', reply_markup=kb)
        return await super().handle()


@form_router.message(WorkTimeStateGroup.set_begin_lanch)
class WorkTimeBeginLanch(MessageHandler):
    @sync_to_async
    def set_begin_lanch(self, department_id, time):
        Department.objects.filter(id=department_id).update(begin_lanch=time)

    async def handle(self) -> typing.Any:
        _data = await self.data['state'].get_data()
        _time_text = self.event.text
        await self.data['state'].set_state(None)
        department_id = _data['department_id']
        if ' ' in _time_text:
            while '  ' in _time_text:
                _time_text = _time_text.replace('  ', ' ')
        if ':' in _time_text:
            _time_text = _time_text.replace(':', ' ')
        try:
            begin_time = datetime.datetime.strptime(_time_text, '%H %M')
        except ValueError:
            await self.message.answer('Введите время в формате чч мм')
        else:
            await self.set_begin_lanch(department_id, begin_time)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Назад',
                        callback_data=DepartmentCallback(
                            action=DepartmentAction.set_work_time,
                            department_id=department_id
                        ).pack()
                    )],
                ]
            )
            await self.event.answer(f'Установлено время {begin_time.strftime("%H:%M")}', reply_markup=kb)
        return await super().handle()


@form_router.message(WorkTimeStateGroup.set_end_lanch)
class WorkTimeEndLanch(MessageHandler):
    @sync_to_async
    def set_end_lanch(self, department_id, time):
        Department.objects.filter(id=department_id).update(end_lanch=time)

    async def handle(self) -> typing.Any:
        _data = await self.data['state'].get_data()
        _time_text = self.event.text
        await self.data['state'].set_state(None)
        department_id = _data['department_id']
        if ' ' in _time_text:
            while '  ' in _time_text:
                _time_text = _time_text.replace('  ', ' ')
        if ':' in _time_text:
            _time_text = _time_text.replace(':', ' ')
        try:
            begin_time = datetime.datetime.strptime(_time_text, '%H %M')
        except ValueError:
            await self.message.answer('Введите время в формате чч мм')
        else:
            await self.set_end_lanch(department_id, begin_time)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Назад',
                        callback_data=DepartmentCallback(
                            action=DepartmentAction.set_work_time,
                            department_id=department_id
                        ).pack()
                    )],
                ]
            )
            await self.event.answer(f'Установлено время {begin_time.strftime("%H:%M")}', reply_markup=kb)
        return await super().handle()


@form_router.message(WorkTimeStateGroup.set_end)
class WorkTimeEnd(MessageHandler):
    @sync_to_async
    def set_end(self, department_id, time):
        Department.objects.filter(id=department_id).update(end=time)

    async def handle(self) -> typing.Any:
        _data = await self.data['state'].get_data()
        _time_text = self.event.text
        await self.data['state'].set_state(None)
        department_id = _data['department_id']
        if ' ' in _time_text:
            while '  ' in _time_text:
                _time_text = _time_text.replace('  ', ' ')
        if ':' in _time_text:
            _time_text = _time_text.replace(':', ' ')
        try:
            begin_time = datetime.datetime.strptime(_time_text, '%H %M')
        except ValueError:
            await self.message.answer('Введите время в формате чч мм')
        else:
            await self.set_end(department_id, begin_time)
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text='Назад',
                        callback_data=DepartmentCallback(
                            action=DepartmentAction.set_work_time,
                            department_id=department_id
                        ).pack()
                    )],
                ]
            )
            await self.event.answer(f'Установлено время {begin_time.strftime("%H:%M")}', reply_markup=kb)
        return await super().handle()


@form_router.message(DepartmentStateGroup.new_name)
class NewNameDepartment(MessageHandler):
    @sync_to_async
    def rename_department(self, old_name, new_name):
        Department.objects.filter(name=old_name).update(name=new_name)

    async def handle(self) -> typing.Any:
        _data = await self.data['state'].get_data()
        await self.data['state'].set_state(None)
        old_name = _data['old_name']
        new_name = self.event.text
        await self.rename_department(old_name, new_name)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text='Назад',
                    callback_data=DepartmentCallback(action=DepartmentAction.list).pack()
                )],
            ]
        )
        await self.event.answer(f'Подразделение {old_name} переименовано в {new_name}', reply_markup=kb)
        return await super().handle()


@form_router.message(DepartmentStateGroup.create)
class NewDepartment(MessageHandler):
    @sync_to_async
    def create_department(self, new_name):
        Department.objects.create(name=new_name)

    async def handle(self) -> typing.Any:
        await self.data['state'].set_state(None)
        new_name = self.event.text
        await self.create_department(new_name)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text='Назад',
                    callback_data=DepartmentCallback(action=DepartmentAction.list).pack()
                )],
            ]
        )
        await self.event.answer(f'Создано подразделение {new_name}', reply_markup=kb)
        return await super().handle()


@sync_to_async
def get_user_by_username(username):
    return TgUser.objects.filter(username=username).first()


@sync_to_async
def transfer_admin(user_id):
    TgUser.objects.filter(id=user_id).update(user_type=UserType.ADMIN.value)


@form_router.message(TransferAdmin.add_admin_state)
class TransferAdminMessageHandler(MessageHandler):

    async def handle(self) -> typing.Any:
        await self.data['state'].set_state(None)
        username = self.event.text
        new_user = await get_user_by_username(username)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='Назад', callback_data=UserCallback(action=UserAction.back).pack())]
            ]
        )
        if new_user:
            await transfer_admin(new_user.id)
            await self.event.answer(f'Пользователь с ником {new_user.username} назначен админом', reply_markup=kb)
            await self.bot.send_message(new_user.tg_id, 'Вы назначены админом')
        else:
            await self.event.answer(f'Пользователь с ником {username} не найден', reply_markup=kb)
        return await super().handle()


@form_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await get_or_create_user(message.from_user)


@form_router.message(Command('menu'))
async def command_menu_handler(message: Message, state: FSMContext) -> None:
    user = await get_or_create_user(message.from_user)
    interface = INTERFACE.get(UserType(user.user_type).value)
    if interface:
        menu_name, menu_kb = interface
        if UserType(user.user_type) is UserType.EMPLOYEE:
            user_status = UserStatus(user.status)
            menu_name = f'Текущий статус: {user_status.label}'
        await message.answer(menu_name, reply_markup=menu_kb)
    else:
        await message.answer('Вы новый пользователь. Дождитесь регистрации от админа')
    await clear_messages(message.bot, message.chat.id, message.message_id)


@form_router.message(StateFilter(None))
async def unknown_command(message: Message, state: FSMContext) -> None:
    await message.answer('Неизвестная команда.\nВоспользуйтесь главным меню - /menu')


async def run_bot():
    dp.include_router(form_router)

    await dp.start_polling(bot)


@sync_to_async
def get_users():
    return list(TgUser.objects.all())


async def monitoring():
    while True:
        print('Мониторим за сотрудниками')
        if bot.session._session and not bot.session._session.closed:
            for user in await get_users():
                msg = None
                department = await get_user_department(user.id)
                if department:
                    now = timezone.now().time()
                    if (
                        not UserStatus(user.status) is UserStatus.BEGIN
                        and (department.begin.hour == now.hour and department.begin.minute == now.minute)
                    ):
                        msg = f'Сотрудник {user.name} {department.name} не на рабочем месте'
                    elif (
                        UserStatus(user.status) is UserStatus.BEGIN_LANCH
                        and (department.end_lanch.hour == now.hour and department.end_lanch.minute == now.minute)
                    ):
                        msg = f'Сотрудник {user.name} {department.name} еще не вернулся с обеда'
                    if msg:
                        try:
                            await bot.send_message(settings.WORK_CHAT_ID, msg)
                        except TelegramBadRequest:
                            pass
        await asyncio.sleep(60)


async def main() -> None:
    await asyncio.gather(
        run_bot(),
        monitoring(),
    )


def run(*args):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())


if __name__ == '__main__':
    run()
