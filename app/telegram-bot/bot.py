"""
Простой Telegram бот для Shorts Maker API
С поддержкой локального Bot API для больших файлов
"""
import asyncio
import aiohttp
import logging
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройки
BOT_TOKEN = "7718723631:AAHapgiCxXnyugZT_s1kH7_b19eqlDDYhTs"  
API_BASE_URL = "http://localhost:8000" 
LOCAL_BOT_API_URL = "http://localhost:8081" 

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния бота
class VideoProcessing(StatesGroup):
    waiting_for_video = State()
    processing = State()


async def download_file_from_telegram(bot: Bot, file_id: str, destination: Path) -> bool:
    """Скачивает файл из Telegram"""
    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, destination)
        return True
    except Exception as e:
        logger.error(f"Ошибка скачивания: {e}")
        return False


async def upload_to_api(file_path: Path, user_id: int) -> Optional[str]:
    """Отправляет файл в API"""
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('file', open(file_path, 'rb'), 
                          filename=file_path.name,
                          content_type='video/mp4')
            data.add_field('min_duration', '30')
            data.add_field('max_duration', '120')
            data.add_field('enable_subtitles', 'false')
            data.add_field('mobile_scale_factor', '1.2')
            
            async with session.post(f"{API_BASE_URL}/api/v1/process", data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get('task_id')
                else:
                    logger.error(f"API ошибка: {resp.status}")
                    return None
    except Exception as e:
        logger.error(f"Ошибка отправки в API: {e}")
        return None


async def create_bot_with_local_api():
    """Создает бота с локальным Bot API если доступен"""
    
    # Проверяем локальный Bot API
    using_local_api = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{LOCAL_BOT_API_URL}", timeout=3) as resp:
                if resp.status == 200:
                    using_local_api = True
                    logger.info("✅ Используем локальный Bot API (до 2GB)")
                else:
                    logger.info("⚠️ Локальный Bot API недоступен, используем стандартный (до 50MB)")
    except Exception as e:
        logger.info(f"⚠️ Локальный Bot API недоступен ({e}), используем стандартный (до 50MB)")
    
    # Создаем бота
    if using_local_api:
        try:
            api_server = TelegramAPIServer.from_base(LOCAL_BOT_API_URL)
            session = AiohttpSession(api=api_server)
            bot = Bot(token=BOT_TOKEN, session=session)
            logger.info("🚀 Бот создан с локальным Bot API")
            return bot, True
        except Exception as e:
            logger.warning(f"❌ Ошибка создания бота с локальным API: {e}")
    
    # Стандартный бот
    bot = Bot(token=BOT_TOKEN)
    logger.info("🚀 Бот создан со стандартным API")
    return bot, False


async def main():
    """Главная функция"""
    
    # Создаем бота с проверкой локального API
    bot, using_local_api = await create_bot_with_local_api()
    dp = Dispatcher(storage=MemoryStorage())
    
    # Лимиты файлов
    max_file_size = 2000000000 if using_local_api else 50000000  # 2GB или 50MB
    max_file_size_mb = max_file_size / (1024 * 1024)

    @dp.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext):
        """Команда /start"""
        api_type = "локальный Bot API (до 2GB)" if using_local_api else "стандартный API (до 50MB)"
        
        await message.answer(
            f"🎬 Привет! Я бот для создания шортсов.\n\n"
            f"📤 Отправь мне видео, и я нарежу его на сегменты!\n\n"
            f"📊 Текущие возможности:\n"
            f"• Максимальный размер файла: {max_file_size_mb:.0f}MB\n"
            f"• Используется: {api_type}\n\n"
            f"📹 Просто отправь видеофайл!"
        )
        await state.set_state(VideoProcessing.waiting_for_video)

    @dp.message(Command("status"))
    async def cmd_status(message: Message):
        """Проверка API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}/api/v1/health") as resp:
                    if resp.status == 200:
                        api_type = "локальный (2GB)" if using_local_api else "стандартный (50MB)"
                        await message.answer(
                            f"✅ API работает!\n"
                            f"🤖 Bot API: {api_type}"
                        )
                    else:
                        await message.answer(f"❌ API недоступен ({resp.status})")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)}")

    @dp.message(F.video, VideoProcessing.waiting_for_video)
    async def handle_video(message: Message, state: FSMContext):
        """Обработка видео"""
        await handle_video_file(message, state, message.video)

    @dp.message(F.document, VideoProcessing.waiting_for_video)
    async def handle_document(message: Message, state: FSMContext):
        """Обработка документов (большие видео)"""
        if not message.document.file_name:
            await message.answer("❌ Не удалось определить тип файла")
            return
            
        # Проверяем что это видео
        file_ext = Path(message.document.file_name).suffix.lower()
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        
        if file_ext not in video_extensions:
            await message.answer(f"❌ Неподдерживаемый формат: {file_ext}")
            return
        
        await handle_video_file(message, state, message.document)

    async def handle_video_file(message: Message, state: FSMContext, file_obj):
        """Универсальная обработка видеофайлов"""
        await state.set_state(VideoProcessing.processing)
        
        # Проверяем размер
        file_size = file_obj.file_size or 0
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size > max_file_size:
            await message.answer(
                f"❌ Файл слишком большой: {file_size_mb:.1f}MB\n"
                f"📏 Максимальный размер: {max_file_size_mb:.0f}MB\n"
                f"💡 {'Попробуйте сжать видео' if using_local_api else 'Требуется локальный Bot API для больших файлов'}"
            )
            await state.set_state(VideoProcessing.waiting_for_video)
            return
        
        # Предупреждение о больших файлах
        if file_size_mb > 100:
            await message.answer(f"📊 Большой файл: {file_size_mb:.1f}MB - обработка займет время...")
        
        status_msg = await message.answer("📥 Скачиваю видео...")
        
        # Скачиваем
        temp_dir = Path("temp_downloads")
        temp_dir.mkdir(exist_ok=True)
        
        filename = getattr(file_obj, 'file_name', None) or f"video_{message.from_user.id}.mp4"
        video_file = temp_dir / filename
        
        if not await download_file_from_telegram(bot, file_obj.file_id, video_file):
            await status_msg.edit_text("❌ Ошибка скачивания")
            await state.set_state(VideoProcessing.waiting_for_video)
            return
        
        # Отправляем в API
        await status_msg.edit_text("🚀 Отправляю в API...")
        task_id = await upload_to_api(video_file, message.from_user.id)
        
        if not task_id:
            await status_msg.edit_text("❌ Ошибка API")
            video_file.unlink(missing_ok=True)
            await state.set_state(VideoProcessing.waiting_for_video)
            return
        
        # Мониторим
        await status_msg.edit_text(f"⏳ Обрабатываю... (ID: {task_id})")
        
        for attempt in range(120):  # 10 минут для больших файлов
            await asyncio.sleep(5)
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{API_BASE_URL}/api/v1/status/{task_id}") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                        else:
                            data = {"status": "error"}
            except:
                data = {"status": "error"}
            
            status = data.get('status', 'unknown')
            progress = data.get('progress', 0)
            
            if status == 'completed':
                segments = data.get('segments_created', 0)
                await status_msg.edit_text(f"✅ Готово! Создано сегментов: {segments}")
                break
            elif status == 'error':
                error = data.get('error_message', 'Неизвестная ошибка')
                await status_msg.edit_text(f"❌ Ошибка: {error}")
                break
            else:
                minutes = (attempt + 1) * 5 // 60
                seconds = (attempt + 1) * 5 % 60
                await status_msg.edit_text(f"⏳ Обрабатываю... {progress}% ({minutes}:{seconds:02d})")
        else:
            await status_msg.edit_text("⏰ Таймаут")
        
        # Очищаем
        video_file.unlink(missing_ok=True)
        await state.set_state(VideoProcessing.waiting_for_video)

    @dp.message(VideoProcessing.waiting_for_video)
    async def handle_other(message: Message):
        """Обработка других сообщений"""
        await message.answer("📹 Отправьте видеофайл для обработки")

    # Проверяем API
    logger.info("Запуск бота...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/api/v1/health") as resp:
                if resp.status == 200:
                    logger.info("✅ API доступен")
                else:
                    logger.warning(f"⚠️ API недоступен ({resp.status})")
    except Exception as e:
        logger.error(f"❌ API недоступен: {e}")

    # Запускаем
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())