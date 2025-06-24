import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile, BufferedInputFile, Message, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from qr_utils import extract_qrs_from_image
from image_utils import create_result_images
import os
import cv2
from config import API_TOKEN

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

user_data = {}
user_media_message_ids = {}
user_cancel_flags = {}

USERS_FILE = 'users.txt'

# Список админов (замени 123456789 на свой user_id)
ADMINS = {437656500,390887899,5319622027}
# Множество всех user_id, с которыми был контакт
all_user_ids = set()

# Загрузка user_id из файла при запуске
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            uid = line.strip()
            if uid.isdigit():
                all_user_ids.add(int(uid))

def save_user_id(user_id):
    if user_id not in all_user_ids:
        with open(USERS_FILE, 'a', encoding='utf-8') as f:
            f.write(f'{user_id}\n')

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Привет! Пришли мне фото с QR-кодами на листе А4.")

@dp.message(Command('cancel'))
async def cancel_handler(message: Message):
    user_cancel_flags[message.from_user.id] = True
    await message.answer("Распознавание прервано по вашему запросу. Вы можете отправить новое изображение.")

@dp.message(lambda m: m.photo or m.document)
async def handle_photo(message: Message, bot: Bot):
    orig_path = 'input.jpg'
    user_cancel_flags[message.from_user.id] = False
    if message.photo:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_path = file.file_path
        file_bytes = await bot.download_file(file_path)
        with open(orig_path, 'wb') as f:
            f.write(file_bytes.read())
    elif message.document:
        file = await bot.get_file(message.document.file_id)
        file_path = file.file_path
        file_bytes = await bot.download_file(file_path)
        ext = os.path.splitext(message.document.file_name)[-1].lower()
        save_path = 'input' + ext
        with open(save_path, 'wb') as f:
            f.write(file_bytes.read())
        if ext in ['.jpg', '.jpeg']:
            orig_path = save_path
        else:
            if os.path.exists('input.jpg'):
                os.remove('input.jpg')
            os.rename(save_path, 'input.jpg')
            orig_path = 'input.jpg'
    else:
        await message.answer("Пожалуйста, отправьте фото или файл с изображением.")
        return
    # Сообщение о начале распознавания + кнопка Cancel
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Cancel", callback_data="cancel_scan"))
    await message.answer("Распознавание QR-кодов началось, пожалуйста, подождите... 🕑", reply_markup=builder.as_markup())
    # Асинхронный запуск сканирования с проверкой на отмену
    await scan_with_cancel(message, orig_path)

async def scan_with_cancel(message: Message, orig_path: str):
    user_id = message.from_user.id
    loop = asyncio.get_event_loop()
    qrs = await loop.run_in_executor(None, extract_qrs_from_image, orig_path)
    if user_cancel_flags.get(user_id):
        await message.answer("Распознавание было прервано. Вы можете отправить новое изображение.")
        return
    if not qrs:
        await message.answer("QR-коды не найдены! Пожалуйста, попробуйте сделать фото ещё раз.")
        return
    if any(qr['data'] is None for qr in qrs):
        await message.answer("Не все QR-коды читаются! Пожалуйста, попробуйте сделать фото ещё раз.")
        return
    await message.answer(f"Найдено QR-кодов: {len(qrs)}. Для каждого будет создана отдельная картинка.")

    # Рисуем зелёные прямоугольники на исходном фото
    img = cv2.imread(orig_path)
    for qr in qrs:
        rect = qr['rect']
        if rect and all(isinstance(x, int) for x in rect):
            x, y, w, h = rect
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 4)
    cv2.imwrite('input_with_qr.jpg', img)
    with open('input_with_qr.jpg', 'rb') as f:
        await message.answer_photo(BufferedInputFile(f.read(), filename='input_with_qr.jpg'), caption='Исходное фото с найденными QR-кодами (зелёным)')

    images = create_result_images(qrs)
    user_data[message.from_user.id] = images
    await send_images(message, images, 0)

async def send_images(message: Message, images, page, user_id=None):
    if user_id is None:
        user_id = message.from_user.id
    batch = images[page*10:(page+1)*10]
    media = []
    for img_path in batch:
        with open(img_path, 'rb') as f:
            img_bytes = f.read()
            media.append(InputMediaPhoto(media=BufferedInputFile(img_bytes, filename=os.path.basename(img_path))))
    if media:
        prev_ids = user_media_message_ids.get(user_id, [])
        for mid in prev_ids:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=mid)
            except Exception:
                pass
        sent = await message.answer_media_group(media)
        user_media_message_ids[user_id] = [m.message_id for m in sent]
        # Кнопки навигации
        builder = InlineKeyboardBuilder()
        if page > 0:
            builder.add(InlineKeyboardButton(text="Back", callback_data=f"back_{page-1}"))
        if len(images) > (page+1)*10:
            builder.add(InlineKeyboardButton(text="Next", callback_data=f"next_{page+1}"))
        builder.add(InlineKeyboardButton(text="Clear", callback_data="clear"))
        await message.answer("Навигация:", reply_markup=builder.as_markup())

@dp.callback_query(lambda c: c.data and (c.data.startswith('next_') or c.data.startswith('back_') or c.data == 'clear' or c.data == 'cancel_scan'))
async def process_callback_nav(callback: CallbackQuery):
    user_id = callback.from_user.id
    if callback.data.startswith('next_'):
        page = int(callback.data.split('_')[1])
        images = user_data.get(user_id, [])
        await send_images(callback.message, images, page, user_id=user_id)
        await callback.answer()
    elif callback.data.startswith('back_'):
        page = int(callback.data.split('_')[1])
        images = user_data.get(user_id, [])
        await send_images(callback.message, images, page, user_id=user_id)
        await callback.answer()
    elif callback.data == 'clear':
        user_data.pop(user_id, None)
        user_media_message_ids.pop(user_id, None)
        await callback.message.answer("Данные очищены. Вы можете отправить новое изображение для распознавания QR-кодов.")
        await callback.answer("Данные очищены")
    elif callback.data == 'cancel_scan':
        user_cancel_flags[callback.from_user.id] = True
        await callback.message.answer("Распознавание прервано по вашему запросу. Вы можете отправить новое изображение.")
        await callback.answer("Распознавание отменено")

@dp.message(~Command('message'))
async def track_user(message: Message):
    user_id = message.from_user.id
    if user_id not in all_user_ids:
        all_user_ids.add(user_id)
        save_user_id(user_id)
    # Этот хендлер больше не мешает обработке команды /message

@dp.message(Command('message'))
async def broadcast_handler(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer('⛔️ У вас нет прав для этой команды.')
        return
    text = message.text[len('/message'):].strip()
    if not text:
        await message.answer('Использование: /message текст_рассылки')
        return
    count = 0
    for uid in all_user_ids:
        try:
            await bot.send_message(uid, text)
            count += 1
        except Exception:
            pass
    await message.answer(f'Рассылка завершена. Сообщение отправлено {count} пользователям.')

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main()) 