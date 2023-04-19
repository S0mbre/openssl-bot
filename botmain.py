import logging
import asyncio
from aiogram import Bot, Dispatcher, F, html
from aiogram.filters import Command, CommandObject
from aiogram.utils import markdown as md
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

from config import CONFIG

# ============================================================ #
# openssl pkcs12 -export -in cert.crt -inkey cert.key -password pass:123123 -out cert1.p12

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
"""

logging.basicConfig(level=logging.INFO)

bot = Bot(token=CONFIG.bot_token.get_secret_value())
dp = Dispatcher(storage=MemoryStorage())

# ============================================================ #

def make_row_keyboard(items: list[str]) -> ReplyKeyboardMarkup:
    row = [KeyboardButton(text=item) for item in items]
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)

def escape_symbols(msg: str) -> str:
    msg_ = msg
    for k, v in ESCAPE_MAP.items():
        msg_ = msg_.replace(k, v)
    return msg_

@dp.message(Command('start'))
async def send_welcome(message: Message):
    await message.answer(BOT_HELP)
    # await message.answer(md.text(md.bold('Fuck'), ('you\\!')), parse_mode='MarkdownV2')

@dp.message(F.text)
async def handler(message: Message):
	await message.answer(message.text)
    
async def main():
    await dp.start_polling(bot, skip_updates=True)

# ============================================================ #

if __name__ == '__main__':
    asyncio.run(main())
