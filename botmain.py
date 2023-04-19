import logging
import asyncio
from aiogram import Bot, Dispatcher, F, html
from aiogram.filters import Command, Text
from aiogram.utils import markdown as md
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, BufferedInputFile, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

from config import CONFIG
import ossl

# ============================================================ #

ESCAPE_MAP = {'_': '\\_', '*': '\\*', '[': '\\[', ']': '\\]', '(': '\\(', ')': '\\)', 
              '~': '\\~', '`': '\\`', '>': '\\>', '#': '\\#', '+': '\\+', '-': '\\-', 
              '=': '\\=', '|': '\\|', '{': '\\{', '}': '\\}', '.': '\\.', '!': '\\!'}

BOT_HELP = \
""" 
⚡ ⓅⓀⒸⓈ ①② Generator ⚡

Бот поможет Вам создать хранилище сертификатов PKCS-12 из сертификата и приватного ключа (PEM) 
при помощи OpenSSL PKCS12: https://www.openssl.org/docs/man1.1.1/man1/pkcs12.html

Для работы бота убедитесь, что у Вас есть:

1. SSL сертификат
2. Приватный ключ к этому сертификату

Оба файла должны быть в формате PEM, т.е. их структура должна быть такой:

-----BEGIN CERTIFICATE-----
<тело ключа>
-----END CERTIFICATE-----

КОМАНДЫ:
- /start: прервать сессию и начать заново, отобразив эту подсказку
- /checkssl: проверить установку OpenSSL
"""

logging.basicConfig(level=logging.INFO)

bot = Bot(token=CONFIG.bot_token.get_secret_value())
dp = Dispatcher(storage=MemoryStorage())

# ============================================================ #

class MyStates(StatesGroup):
    start_state = State()
    sending_crt_state = State()
    sending_key_state = State()
    setting_name_state = State()
    setting_pw_state = State()

START_BUTTONS = ['Проверка SSL', 'Начать', 'Сброс']
CRT_BUTTONS = ['Сброс', 'Загрузить повторно', 'Далее']
NAME_BUTTONS = ['Сброс', 'Изменить имя', 'Далее']
PW_BUTTONS = ['Сброс', 'Изменить пароль', 'Завершить']

# ============================================================ #

def make_keyboard(items: list[str], placeholder: str = 'Выберите действие') -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(*[KeyboardButton(text=item) for item in items])
    builder.adjust(min(3, len(items)))
    return builder.as_markup(resize_keyboard=True, input_field_placeholder=placeholder or None)

def escape_symbols(msg: str) -> str:
    msg_ = msg
    for k, v in ESCAPE_MAP.items():
        msg_ = msg_.replace(k, v)
    return msg_

@dp.message(Command(commands=['start', 'help']))
@dp.message(Text(text=['Сброс']))
async def start(message: Message, state: FSMContext):
    if message.text != '/help':
        # await state.clear()
        await state.set_state(MyStates.start_state)
    await message.answer(BOT_HELP, reply_markup=make_keyboard(START_BUTTONS))

@dp.message(MyStates.start_state, Text(text='Проверка SSL'))
async def checkssl(message: Message):
    res = ossl.check_ossl()
    if res:
        await message.answer(f'OpenSSL установлен: {res}', 
                             reply_markup=make_keyboard(START_BUTTONS))
    else:
        await message.answer('OpenSSL не установлен или неправильно работает', 
                             reply_markup=make_keyboard(START_BUTTONS))

@dp.message(MyStates.start_state, Text(text='Начать'))
async def send_crt(message: Message, state: FSMContext):
    await state.set_state(MyStates.sending_crt_state)
    await message.answer('Отправьте текст или файл SSL сертификата (.crt, .pem)', 
                         reply_markup=ReplyKeyboardRemove())

@dp.message(MyStates.sending_crt_state, F.text.startswith('-----BEGIN CERTIFICATE-----'))
async def send_crt_text(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_crt_state)
    await state.set_data({'crt': message.text})    
    await message.answer('Получен SSL сертификат (.crt, .pem)', 
                         reply_markup=make_keyboard(CRT_BUTTONS))

@dp.message(MyStates.sending_crt_state, F.document)
async def send_crt_file(message: Message, state: FSMContext, bot: Bot):
    # await state.set_state(MyStates.sending_crt_state)
    file = await bot.get_file(message.document.file_id)
    iostream = await bot.download_file(file.file_path)
    await state.set_data({'crt': iostream.getvalue().decode(ossl.ENC)})
    await message.answer(f'Получен SSL сертификат (.crt, .pem): {message.document.file_name}',
                         reply_markup=make_keyboard(CRT_BUTTONS))  

@dp.message(MyStates.sending_crt_state, Text(text='Загрузить повторно'))
async def send_crt_text_reload(message: Message, state: FSMContext):
    await state.set_state(MyStates.sending_crt_state)
    await message.answer('Отправьте текст или файл SSL сертификата (.crt, .pem)', reply_markup=ReplyKeyboardRemove())

@dp.message(MyStates.sending_crt_state, Text(text='Далее'))
async def crt_next(message: Message, state: FSMContext):
    await state.set_state(MyStates.sending_key_state)
    # await message.answer('Отправьте текст или файл приватного ключа (.key, .pem)', reply_markup=ReplyKeyboardRemove())
    data = await state.get_data()
    await message.answer(data['crt'], reply_markup=ReplyKeyboardRemove())
        
      
    
async def main():
    await dp.start_polling(bot, skip_updates=True)

# ============================================================ #

if __name__ == '__main__':
    asyncio.run(main())
