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
from aiogram.utils.chat_action import ChatActionMiddleware, ChatActionSender

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

1. SSL сертификат ИЛИ цепочка доверенных сертификатов
2. Приватный ключ к этому сертификату / сертификатам в цепочке

Оба файла должны быть в формате PEM, т.е. их структура должна быть такой:

-----BEGIN ... -----
<тело ключа>
-----END ... -----

Нажмите или наберите "Начать", чтобы приступить. 
В любое время нажмите / наберите "Сброс", чтобы сбросить операцию и вернуться к началу.
"""

logging.basicConfig(level=logging.INFO)

bot = Bot(token=CONFIG.bot_token.get_secret_value())
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(ChatActionMiddleware())

# ============================================================ #

class MyStates(StatesGroup):
    start_state = State()
    sending_crt_state = State()
    sending_key_state = State()
    sending_chain_state = State()
    setting_name_state = State()
    setting_pw_state = State()

START_BUTTONS = ['Проверка SSL', 'Начать', 'Сброс']
CRT_BUTTONS = ['Сброс', 'Загрузить повторно', 'Далее']
SKIP_BUTTONS = ['Пропустить']
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

# ================ 1 - СТАРТ

@dp.message(Command(commands=['start', 'help']))
@dp.message(Text(text=['Сброс']))
async def start(message: Message, state: FSMContext):
    if message.text != '/help':
        await state.clear()
        await state.set_state(MyStates.start_state)
    await message.answer(BOT_HELP, reply_markup=make_keyboard(START_BUTTONS))

# ================ 2 - ПРОВЕРКА OPENSSL

@dp.message(MyStates.start_state, Text(text='Проверка SSL'))
async def checkssl(message: Message):
    res = ossl.check_ossl()
    if res:
        await message.reply(f'👍 OpenSSL установлен: {res}', 
                             reply_markup=make_keyboard(START_BUTTONS))
    else:
        await message.reply('⛔ OpenSSL не установлен или неправильно работает', 
                             reply_markup=make_keyboard(START_BUTTONS))
        
# ================ 3 - ОТПРАВКА ОТКРЫТОГО КЛЮЧА (СЕРТИФИКАТА)

@dp.message(MyStates.start_state, Text(text='Начать'))
async def send_crt(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MyStates.sending_crt_state)
    await message.answer('✍ Отправьте текст или файл SSL сертификата (.crt, .pem) или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))

@dp.message(MyStates.sending_crt_state, F.text.startswith('-----BEGIN CERTIFICATE-----'))
async def send_crt_text(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_crt_state)
    await state.update_data({'crt': message.text})    
    await message.answer('✅ Получен SSL сертификат (.crt, .pem)', 
                         reply_markup=make_keyboard(CRT_BUTTONS))

@dp.message(MyStates.sending_crt_state, F.document)
async def send_crt_file(message: Message, state: FSMContext, bot: Bot):
    # await state.set_state(MyStates.sending_crt_state)
    file = await bot.get_file(message.document.file_id)
    iostream = await bot.download_file(file.file_path)
    await state.update_data({'crt': iostream.getvalue().decode(ossl.ENC)})
    await message.answer(f'✅ Получен SSL сертификат (.crt, .pem): {message.document.file_name}',
                         reply_markup=make_keyboard(CRT_BUTTONS))  
    
@dp.message(MyStates.sending_crt_state, Text(text='Пропустить'))
async def send_crt_skip(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_crt_state)
    await state.update_data({'crt': None})    
    await message.reply('✘ SSL сертификат пропущен', 
                         reply_markup=make_keyboard(CRT_BUTTONS))

@dp.message(MyStates.sending_crt_state, Text(text='Загрузить повторно'))
async def send_crt_text_reload(message: Message, state: FSMContext):
    await state.update_data({'crt': None})
    await message.answer('✍ Отправьте текст или файл SSL сертификата (.crt, .pem) или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))
        
# ================ 3 - ОТПРАВКА ЗАКРЫТОГО (ПРИВАТНОГО) КЛЮЧА

@dp.message(MyStates.sending_crt_state, Text(text='Далее'))
async def crt_next(message: Message, state: FSMContext):
    await state.set_state(MyStates.sending_key_state)
    await message.answer('✍ Отправьте текст или файл приватного ключа (.key, .pem) или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))
    # data = await state.get_data()
    # await message.answer(data['crt'], reply_markup=ReplyKeyboardRemove())
      
@dp.message(MyStates.sending_key_state, F.text.contains('PRIVATE KEY-----'))
async def send_priv_text(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_priv_state)
    await state.update_data({'priv': message.text})    
    await message.answer('✅ Получен приватный ключ (.key, .pem)', 
                         reply_markup=make_keyboard(CRT_BUTTONS))

@dp.message(MyStates.sending_key_state, F.document)
async def send_priv_file(message: Message, state: FSMContext, bot: Bot):
    file = await bot.get_file(message.document.file_id)
    iostream = await bot.download_file(file.file_path)
    await state.update_data({'priv': iostream.getvalue().decode(ossl.ENC)})
    await message.answer(f'✅ Получен приватный ключ (.key, .pem): {message.document.file_name}',
                         reply_markup=make_keyboard(CRT_BUTTONS))  
    
@dp.message(MyStates.sending_key_state, Text(text='Пропустить'))
async def send_priv_skip(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_priv_state)
    await state.update_data({'priv': None})    
    await message.reply('✘ Приватный ключ пропущен', 
                         reply_markup=make_keyboard(CRT_BUTTONS))

@dp.message(MyStates.sending_key_state, Text(text='Загрузить повторно'))
async def send_priv_text_reload(message: Message, state: FSMContext):
    await state.update_data({'priv': None})  
    await message.answer('✍ Отправьте текст или файл приватного ключа (.key, .pem) или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))

# ================ 4 - ОТПРАВКА ЦЕПОЧКИ СЕРТИФИКАТОВ

@dp.message(MyStates.sending_key_state, Text(text='Далее'))
async def priv_next(message: Message, state: FSMContext):
    await state.set_state(MyStates.sending_chain_state)
    await message.answer('✍ Отправьте текст или файл цепочки сертификатов (.crt, .pem) или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))
    # data = await state.get_data()
    # await message.answer(data['crt'], reply_markup=ReplyKeyboardRemove())
      
@dp.message(MyStates.sending_chain_state, F.text.startswith('-----BEGIN'))
async def send_chain_text(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_priv_state)
    await state.update_data({'chain': message.text})    
    await message.answer('✅ Получена цепочка сертификатов', 
                         reply_markup=make_keyboard(CRT_BUTTONS))

@dp.message(MyStates.sending_chain_state, F.document)
async def send_chain_file(message: Message, state: FSMContext, bot: Bot):
    file = await bot.get_file(message.document.file_id)
    iostream = await bot.download_file(file.file_path)
    await state.update_data({'chain': iostream.getvalue().decode(ossl.ENC)})
    await message.answer(f'✅ Получена цепочка сертификатов: {message.document.file_name}',
                         reply_markup=make_keyboard(CRT_BUTTONS))  
    
@dp.message(MyStates.sending_chain_state, Text(text='Пропустить'))
async def send_chain_skip(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_priv_state)
    await state.update_data({'chain': None})    
    await message.reply('✘ Цепочка сертификатов пропущена', 
                         reply_markup=make_keyboard(CRT_BUTTONS))

@dp.message(MyStates.sending_chain_state, Text(text='Загрузить повторно'))
async def send_chain_text_reload(message: Message, state: FSMContext):
    await state.update_data({'chain': None})  
    await message.answer('✍ Отправьте текст или файл цепочки сертификатов (.crt, .pem) или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))
    
# ================ 5 - УКАЗАНИЕ ИМЕНИ (АЛИАСА)

@dp.message(MyStates.sending_chain_state, Text(text='Далее'))
async def chain_next(message: Message, state: FSMContext):
    await state.set_state(MyStates.setting_name_state)
    await message.answer('✍ Укажите имя (алиас) для сертификата или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))
    
@dp.message(MyStates.setting_name_state, Text(text='Пропустить'))
async def set_name_skip(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_priv_state)
    await state.update_data({'name': None})    
    await message.reply('✘ Имя сертификата пропущено', 
                         reply_markup=make_keyboard(NAME_BUTTONS))
    
@dp.message(MyStates.setting_name_state, Text(text='Изменить имя'))
async def set_name_reload(message: Message, state: FSMContext):
    await state.update_data({'name': None})  
    await message.answer('✍ Укажите имя (алиас) для сертификата или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))
    
@dp.message(MyStates.setting_name_state, F.text.regexp(r'[A-Za-z]+'))
async def set_name_text(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_priv_state)
    await state.update_data({'name': message.text.strip()})    
    await message.answer(f'✅ Имя сертификата: "{message.text.strip()}"', 
                         reply_markup=make_keyboard(NAME_BUTTONS))
    
# ================ 6 - УКАЗАНИЕ ПАРОЛЯ

@dp.message(MyStates.setting_name_state, Text(text='Далее'))
async def set_name_next(message: Message, state: FSMContext):
    await state.set_state(MyStates.setting_pw_state)
    await message.answer('✍ Укажите пароль для сертификата или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))
    
@dp.message(MyStates.setting_pw_state, Text(text='Пропустить'))
async def set_pw_skip(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_priv_state)
    await state.update_data({'pw': None})    
    await message.reply('✘ Пароль пропущен', 
                         reply_markup=make_keyboard(PW_BUTTONS))
    
@dp.message(MyStates.setting_pw_state, Text(text='Изменить пароль'))
async def set_pw_reload(message: Message, state: FSMContext):
    await state.update_data({'pw': None})  
    await message.answer('✍ Укажите пароль для сертификата или нажмите кнопку "Пропустить", если его нет', 
                         reply_markup=make_keyboard(SKIP_BUTTONS))
    
@dp.message(MyStates.setting_pw_state, F.text.regexp(r'[A-Za-z0-9\!\@\#\$\%\^\&\*\(\)\-\_\+\=\/\.\,\<\>\[\]\?\;\'\"]+'))
async def set_pw_text(message: Message, state: FSMContext):
    # await state.set_state(MyStates.sending_priv_state)
    await state.update_data({'pw': message.text.strip()})    
    await message.answer(f'✅ Пароль сертификата: "{message.text.strip()}"', 
                         reply_markup=make_keyboard(PW_BUTTONS))
    
# ================ 7 - ЗАВЕРШЕНИЕ

@dp.message(MyStates.setting_pw_state, Text(text='Завершить'))
async def make_p12(message: Message, state: FSMContext, bot: Bot):
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        data = await state.get_data()
        cert = data.get('crt', None)
        certchain = data.get('chain', None)
        key = data.get('priv', None)
        alias = data.get('name', None)
        pw = data.get('pw', None)
        # logging.info(data)
        await state.clear()
        await state.set_state(MyStates.start_state)
        try:
            buf = ossl.make_pkcs12(cert, certchain, key, alias, pw)        
        except Exception as err:
            await message.answer(f'⛔ Ошибка генерации сертификата:{ossl.NL}{str(err)}', 
                                reply_markup=ReplyKeyboardRemove())
            await message.answer(BOT_HELP, reply_markup=make_keyboard(START_BUTTONS))
            return
        await message.answer_document(BufferedInputFile(buf, filename='cert.p12'), 
                                    caption='🤲 Ваш сертификат готов',
                                    reply_markup=ReplyKeyboardRemove())

# ============================================================ #

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
