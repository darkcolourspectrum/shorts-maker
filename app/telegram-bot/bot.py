"""
Telegram бот для Shorts Maker - ИСПРАВЛЕННАЯ ЗАГРУЗКА ФАЙЛОВ
Правильная работа с локальным Bot API и загрузкой файлов
"""
import asyncio
import aiohttp
import logging
import os
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройки
BOT_TOKEN = "7718723631:AAHapgiCxXnyugZT_s1kH7_b19eqlDDYhTs"
API_BASE_URL = "http://localhost:8000"
LOCAL_BOT_API_URL = "http://localhost:8081"

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shorts_bot")

# Состояния
class VideoProcessing(StatesGroup):
    waiting_for_video = State()
    processing = State()

async def test_local_bot_api() -> bool:
    """Тестируем локальный Bot API"""
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Проверяем что сервер отвечает
            async with session.get(LOCAL_BOT_API_URL) as resp:
                if resp.status in [200, 404]:  # 404 тоже означает что сервер работает
                    logger.info("Локальный Bot API отвечает")
                    return True
    except Exception as e:
        logger.warning(f"Локальный Bot API недоступен: {e}")
    
    return False

async def create_bot():
    """Создает бота с локальным API если доступен"""
    
    logger.info("Проверяем доступность локального Bot API...")
    local_api_available = await test_local_bot_api()
    
    if local_api_available:
        try:
            logger.info("Подключаемся к локальному Bot API...")
            api_server = TelegramAPIServer.from_base(LOCAL_BOT_API_URL)
            session = AiohttpSession(api=api_server)
            bot = Bot(token=BOT_TOKEN, session=session)
            
            # Проверяем подключение
            me = await bot.get_me()
            logger.info(f"✅ Локальный Bot API: @{me.username} (файлы до 2GB)")
            logger.info(f"🔗 Сервер: {LOCAL_BOT_API_URL}")
            return bot, True
            
        except Exception as e:
            logger.error(f"❌ Ошибка локального API: {e}")
    
    # Fallback на стандартный API
    logger.info("Используем стандартный Telegram API...")
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    logger.info(f"✅ Стандартный API: @{me.username} (файлы до 50MB)")
    return bot, False

async def download_file_properly(bot: Bot, file_id: str, destination: Path, using_local_api: bool) -> bool:
    """
    Правильно скачивает файл с учетом типа API
    """
    try:
        logger.info(f"Получаем информацию о файле: {file_id}")
        
        if using_local_api:
            # Для локального API - сначала скачиваем файл ЧЕРЕЗ Bot API
            # Это заставляет Bot API сохранить файл локально
            
            # 1. Получаем информацию о файле
            file_info = await bot.get_file(file_id)
            if not file_info.file_path:
                logger.error("Не удалось получить путь к файлу")
                return False
            
            logger.info(f"Путь к файлу: {file_info.file_path}")
            
            # 2. Сначала делаем запрос getFile чтобы Bot API скачал файл
            timeout = aiohttp.ClientTimeout(total=120)  # 2 минуты на скачивание
            async with aiohttp.ClientSession(timeout=timeout) as session:
                get_file_url = f"{LOCAL_BOT_API_URL}/bot{BOT_TOKEN}/getFile"
                data = {"file_id": file_id}
                
                logger.info("Запрашиваем у Bot API скачивание файла...")
                async with session.post(get_file_url, json=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get('ok'):
                            logger.info("Bot API подтвердил наличие файла")
                        else:
                            logger.error(f"Bot API ошибка: {result}")
                            return False
                    else:
                        logger.error(f"Ошибка getFile: {resp.status}")
                        return False
                
                # 3. Теперь скачиваем файл через стандартный метод
                logger.info("Скачиваем файл через Bot API...")
                try:
                    await bot.download_file(file_info.file_path, destination)
                    size_mb = destination.stat().st_size / (1024 * 1024)
                    logger.info(f"✅ Файл скачан через локальный API: {size_mb:.1f}MB")
                    return True
                except Exception as e:
                    logger.error(f"Ошибка download_file: {e}")
                    
                    # 4. Альтернативный способ - прямое скачивание
                    file_url = f"{LOCAL_BOT_API_URL}/file/bot{BOT_TOKEN}/{file_info.file_path}"
                    logger.info(f"Пробуем прямое скачивание: {file_url}")
                    
                    async with session.get(file_url) as resp:
                        if resp.status == 200:
                            with open(destination, 'wb') as f:
                                async for chunk in resp.content.iter_chunked(8192):
                                    f.write(chunk)
                            size_mb = destination.stat().st_size / (1024 * 1024)
                            logger.info(f"✅ Файл скачан напрямую: {size_mb:.1f}MB")
                            return True
                        else:
                            logger.error(f"Прямое скачивание не удалось: {resp.status}")
                            return False
        else:
            # Для стандартного API - обычное скачивание
            file_info = await bot.get_file(file_id)
            await bot.download_file(file_info.file_path, destination)
            size_mb = destination.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Файл скачан через стандартный API: {size_mb:.1f}MB")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка скачивания файла: {e}")
        return False

async def send_to_api(file_path: Path) -> Optional[str]:
    """Отправляет видео в API"""
    try:
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        logger.info(f"Отправляем файл в API: {file_path.name} ({file_size_mb:.1f}MB)")
        
        timeout = aiohttp.ClientTimeout(total=600)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = aiohttp.FormData()
            
            with open(file_path, 'rb') as f:
                data.add_field('file', f, filename=file_path.name, content_type='video/mp4')
            
            data.add_field('algorithm', 'multi_shorts')
            data.add_field('min_duration', '30')
            data.add_field('max_duration', '90')
            data.add_field('enable_subtitles', 'false')
            data.add_field('mobile_scale_factor', '1.2')
            
            async with session.post(f"{API_BASE_URL}/api/v1/process", data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    task_id = result.get('task_id')
                    logger.info(f"✅ Файл принят API, task_id: {task_id}")
                    return task_id
                else:
                    error_text = await resp.text()
                    logger.error(f"❌ API ошибка {resp.status}: {error_text}")
                    return None
                    
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в API: {e}")
        return None

async def monitor_progress(task_id: str, message: Message) -> dict:
    """Мониторит прогресс обработки"""
    logger.info(f"Мониторим задачу: {task_id}")
    
    for attempt in range(120):  # 10 минут
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{API_BASE_URL}/api/v1/status/{task_id}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                    else:
                        data = {"status": "error", "message": f"HTTP {resp.status}"}
        except Exception as e:
            data = {"status": "error", "message": str(e)}
        
        status = data.get('status', 'unknown')
        progress = data.get('progress', 0)
        message_text = data.get('message', '')
        
        elapsed_min = (attempt + 1) * 5 // 60
        elapsed_sec = (attempt + 1) * 5 % 60
        
        if status == 'completed':
            segments = data.get('segments_created', 0)
            await message.edit_text(
                f"✅ Обработка завершена!\n"
                f"📹 Создано сегментов: {segments}\n"
                f"⏱️ Время: {elapsed_min}:{elapsed_sec:02d}"
            )
            return data
            
        elif status == 'error':
            error_msg = data.get('error_message', 'Неизвестная ошибка')
            await message.edit_text(
                f"❌ Ошибка обработки:\n{error_msg}\n"
                f"⏱️ Время: {elapsed_min}:{elapsed_sec:02d}"
            )
            return data
            
        else:
            if attempt % 2 == 0:  # Обновляем каждые 10 секунд
                try:
                    await message.edit_text(
                        f"🔄 Обрабатываю видео...\n"
                        f"📊 Прогресс: {progress}%\n"
                        f"📝 {message_text}\n"
                        f"⏱️ {elapsed_min}:{elapsed_sec:02d}"
                    )
                except Exception:
                    pass
        
        await asyncio.sleep(5)
    
    await message.edit_text("⏰ Таймаут обработки")
    return {"status": "timeout"}

async def main():
    """Главная функция"""
    logger.info("🚀 Запуск Shorts Maker Bot...")
    
    # Проверяем основной API
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{API_BASE_URL}/api/v1/health") as resp:
                if resp.status != 200:
                    logger.error(f"❌ Основной API недоступен: {resp.status}")
                    return
                logger.info("✅ Основной API доступен")
    except Exception as e:
        logger.error(f"❌ Основной API недоступен: {e}")
        return
    
    # Создаем бота
    bot, using_local_api = await create_bot()
    dp = Dispatcher(storage=MemoryStorage())
    
    # Настройки лимитов
    if using_local_api:
        max_size = 2_000_000_000  # 2GB
        max_size_mb = 2000
        api_info = "локальный Bot API (до 2GB)"
    else:
        max_size = 50_000_000     # 50MB
        max_size_mb = 50
        api_info = "стандартный API (до 50MB)"
    
    logger.info(f"📊 Лимит файлов: {max_size_mb}MB")

    @dp.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext):
        await message.answer(
            f"🎬 Привет! Я создаю шортсы из видео.\n\n"
            f"📊 Текущие настройки:\n"
            f"• Лимит файлов: {max_size_mb}MB\n"
            f"• API: {api_info}\n"
            f"• Мобильная адаптация 9:16\n"
            f"• Умная нарезка по сценам\n\n"
            f"📤 Отправьте видеофайл!"
        )
        await state.set_state(VideoProcessing.waiting_for_video)

    @dp.message(Command("status"))  
    async def cmd_status(message: Message):
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{API_BASE_URL}/api/v1/health") as resp:
                    api_status = "✅ работает" if resp.status == 200 else f"❌ {resp.status}"
                
                async with session.get(LOCAL_BOT_API_URL) as resp:
                    bot_api_status = "✅ работает" if resp.status in [200, 404] else f"❌ {resp.status}"
        except Exception:
            api_status = "❌ недоступен"
            bot_api_status = "❌ недоступен"
            
        await message.answer(
            f"📊 Статус сервисов:\n\n"
            f"🔧 Основной API: {api_status}\n"
            f"🤖 Bot API: {bot_api_status}\n"
            f"📁 Режим: {api_info}\n"
            f"📊 Лимит: {max_size_mb}MB"
        )

    @dp.message(F.video, VideoProcessing.waiting_for_video)
    async def handle_video(message: Message, state: FSMContext):
        await handle_file(message, state, message.video)

    @dp.message(F.document, VideoProcessing.waiting_for_video)
    async def handle_document(message: Message, state: FSMContext):
        if not message.document.file_name:
            await message.answer("❌ Не удалось определить тип файла")
            return
            
        ext = Path(message.document.file_name).suffix.lower()
        video_exts = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        
        if ext not in video_exts:
            await message.answer(f"❌ Неподдерживаемый формат: {ext}")
            return
            
        await handle_file(message, state, message.document)

    async def handle_file(message: Message, state: FSMContext, file_obj):
        await state.set_state(VideoProcessing.processing)
        
        file_size = file_obj.file_size or 0
        file_size_mb = file_size / (1024 * 1024)
        
        logger.info(f"Обрабатываем файл: {file_size_mb:.1f}MB (лимит: {max_size_mb}MB)")
        
        # Проверяем размер
        if file_size > max_size:
            await message.answer(
                f"❌ Файл слишком большой: {file_size_mb:.1f}MB\n"
                f"📊 Максимум: {max_size_mb}MB\n"
                f"🔧 Режим: {api_info}"
            )
            await state.set_state(VideoProcessing.waiting_for_video)
            return
        
        if file_size_mb > 100:
            await message.answer(f"📊 Большой файл ({file_size_mb:.1f}MB) - ждите...")
        
        status_msg = await message.answer("📥 Скачиваю видео...")
        
        # Подготавливаем папку
        temp_dir = Path("temp_downloads")
        temp_dir.mkdir(exist_ok=True)
        
        filename = getattr(file_obj, 'file_name', None) or f"video_{message.from_user.id}_{file_obj.file_id[:8]}.mp4"
        video_file = temp_dir / filename
        
        # ПРАВИЛЬНО скачиваем файл
        logger.info(f"Скачиваем через {'локальный' if using_local_api else 'стандартный'} API...")
        if not await download_file_properly(bot, file_obj.file_id, video_file, using_local_api):
            await status_msg.edit_text("❌ Ошибка скачивания файла")
            await state.set_state(VideoProcessing.waiting_for_video)
            return
        
        # Отправляем в API
        await status_msg.edit_text("🚀 Отправляю в API...")
        task_id = await send_to_api(video_file)
        
        if not task_id:
            await status_msg.edit_text("❌ Ошибка API")
            video_file.unlink(missing_ok=True)
            await state.set_state(VideoProcessing.waiting_for_video)
            return
        
        # Мониторим
        await status_msg.edit_text(f"🔄 Обрабатываю...\n📋 ID: {task_id}")
        result = await monitor_progress(task_id, status_msg)
        
        # Результаты
        if result.get('status') == 'completed':
            await message.answer(
                f"🎉 Готово!\n"
                f"📁 Скачать: {API_BASE_URL}/api/v1/telegram/download-zip/{task_id}\n"
                f"🌐 Веб: {API_BASE_URL}/docs"
            )
        
        # Очищаем
        video_file.unlink(missing_ok=True)
        await state.set_state(VideoProcessing.waiting_for_video)

    @dp.message(VideoProcessing.waiting_for_video)
    async def handle_other(message: Message):
        await message.answer("📹 Отправьте видеофайл для обработки")

    logger.info(f"🤖 Бот готов! Лимит: {max_size_mb}MB")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())