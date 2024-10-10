import asyncio
from asgiref.sync import sync_to_async

from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from django.conf import settings

from bot.models import UserType, TgUser

form_router = Router()


INTERFACE = {
    UserType.ADMIN.value: {
        'Новые пользователи': {
            'Принять как сотрудника': {},
            'Принять как Руководителя': {},
            'Принять как Директора': {},
            'Отказать в регистрации': {},
        },
        'Зарегистрированные пользователи': {
            'Директора (список директоров с кнопками под ними)': {},
            'Руководители': {},
            'Сотрудники': {},
        },
        'Список подразделений': {
            'Сотрудники': {},
            'Установить рабочее время для подразделения': {},
            'Переименовать подразделение': {},
            'Удалить подразделение': {},
            'Создать новое подразделение': {},
        }
    },
    UserType.EMPLOYEE.value: {},
    UserType.MANAGER.value: {},
    UserType.DIRECTOR.value: {},
}


@sync_to_async
def get_user(tg_id):
    return TgUser.objects.filter(tg_id=tg_id).first()


@form_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=settings.TOKEN_BOT, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(form_router)

    # And the run events dispatching
    await dp.start_polling(bot)


def run(*args):
    asyncio.run(main())


if __name__ == '__main__':
    run()
