"""
Telegram бот для Shorts Maker - PRODUCTION VERSION
Корректная работа с локальным Bot API для файлов до 2GB
"""
import asyncio
import aiohttp
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN", "7718723631:AAHapgiCxXnyugZT_s1kH7_b19eqlDDYhTs")

# Определяем окружение
IS_DOCKER = os.path.exists('/.dockerenv')
if IS_DOCKER:
    API_BASE_URL = "http://shorts-maker-api:8000"
    LOCAL_BOT_API_URL = "http://telegram-bot-api:8081"
else:
    API_BASE_URL = "http://localhost:8000"
    LOCAL_BOT_API_URL = "http://localhost:8081"

# Папка для временных файлов
TEMP_DIR = Path("/app/storage/temp/bot_downloads") if IS_DOCKER else Path("./temp_downloads")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shorts_bot")

# Состояния
class VideoProcessing(StatesGroup):
    waiting_for_video = State()
    processing = State()


async def check_bot_api() -> bool:
    """Проверяет доступность локального Bot API"""
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"{LOCAL_BOT_API_URL}/bot{BOT_TOKEN}/getMe"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('ok'):
                        logger.info(f"Bot API available: {data.get('result', {}).get('username')}")
                        return True
    except Exception as e:
        logger.warning(f"Bot API check failed: {e}")
    return False


async def create_bot() -> Tuple[Bot, bool]:
    """Создает бота с правильной конфигурацией"""
    
    local_api_available = await check_bot_api()
    
    if local_api_available:
        try:
            # Создаем API сервер для локального Bot API
            api_server = TelegramAPIServer.from_base(LOCAL_BOT_API_URL)
            
            # Создаем сессию БЕЗ параметра timeout - aiogram сам управляет таймаутами
            # Таймауты будут установлены на уровне aiohttp при скачивании файлов
            session = AiohttpSession(api=api_server)
            
            # Создаем бота с кастомной сессией
            bot = Bot(token=BOT_TOKEN, session=session)
            
            # Проверяем работу
            me = await bot.get_me()
            logger.info(f"LOCAL Bot API connected: @{me.username} (2GB support)")
            return bot, True
            
        except Exception as e:
            logger.error(f"Failed to setup local API: {e}")
    
    # Fallback на стандартный API
    logger.info("Using standard Telegram API (50MB limit)")
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    logger.info(f"STANDARD API connected: @{me.username}")
    return bot, False


async def download_file_from_bot_api(file_path: str, destination: Path, bot_token: str) -> bool:
    """Прямое скачивание файла с локального Bot API"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Создаем сессию с большими таймаутами
            timeout = aiohttp.ClientTimeout(
                total=3600,      # 1 час на весь запрос
                connect=30,      # 30 секунд на подключение
                sock_read=600    # 10 минут на чтение
            )
            
            # ВАЖНО: Убираем лишние части пути
            # file_path может быть как "videos/file_0.mp4" так и полный путь
            # Нужно извлечь только относительную часть
            if file_path.startswith('/var/lib/telegram-bot-api/'):
                # Убираем префикс и токен из пути
                parts = file_path.split('/')
                # Ищем videos/photos/documents/etc и берем оттуда
                for i, part in enumerate(parts):
                    if part in ['videos', 'photos', 'documents', 'video_notes', 'voice', 'animations', 'audio']:
                        file_path = '/'.join(parts[i:])
                        break
            
            # Убираем начальный слеш если есть
            file_path = file_path.lstrip('/')
            
            # Формируем правильный URL
            url = f"{LOCAL_BOT_API_URL}/file/bot{bot_token}/{file_path}"
            logger.info(f"Downloading from: {url} (attempt {attempt + 1}/{max_retries})")
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        total_size = int(resp.headers.get('Content-Length', 0))
                        downloaded = 0
                        chunk_size = 1024 * 1024  # 1MB chunks
                        start_time = time.time()
                        last_log_time = start_time
                        
                        with open(destination, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(chunk_size):
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Логируем прогресс каждые 3 секунды
                                current_time = time.time()
                                if current_time - last_log_time > 3:
                                    elapsed = current_time - start_time
                                    speed = downloaded / elapsed / (1024*1024) if elapsed > 0 else 0
                                    progress = (downloaded / total_size * 100) if total_size > 0 else 0
                                    logger.info(
                                        f"Download progress: {progress:.1f}% "
                                        f"({downloaded/(1024*1024):.1f}/{total_size/(1024*1024):.1f}MB) "
                                        f"Speed: {speed:.1f}MB/s"
                                    )
                                    last_log_time = current_time
                        
                        # Финальная проверка
                        actual_size = destination.stat().st_size
                        elapsed = time.time() - start_time
                        avg_speed = actual_size / elapsed / (1024*1024) if elapsed > 0 else 0
                        
                        logger.info(
                            f"Download complete: {actual_size/(1024*1024):.1f}MB "
                            f"in {elapsed:.1f}s (avg {avg_speed:.1f}MB/s)"
                        )
                        
                        # Проверяем целостность
                        if total_size > 0 and abs(actual_size - total_size) > 1024:  # 1KB tolerance
                            logger.warning(f"Size mismatch: expected {total_size}, got {actual_size}")
                            if attempt < max_retries - 1:
                                destination.unlink(missing_ok=True)
                                await asyncio.sleep(5 * (attempt + 1))  # Увеличиваем задержку
                                continue
                        
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(f"HTTP {resp.status}: {error_text[:200]}")
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout on attempt {attempt + 1}")
        except Exception as e:
            logger.error(f"Download error: {e}")
        
        if attempt < max_retries - 1:
            wait_time = 5 * (attempt + 1)
            logger.info(f"Retrying in {wait_time} seconds...")
            await asyncio.sleep(wait_time)
    
    return False


async def download_file(bot: Bot, file_id: str, destination: Path, using_local_api: bool) -> bool:
    """Универсальное скачивание файла"""
    try:
        # Получаем информацию о файле
        logger.info(f"Getting file info for: {file_id[:20]}...")
        file_info = await bot.get_file(file_id)
        
        if not file_info.file_path:
            logger.error("No file_path in response")
            return False
        
        file_size_mb = (file_info.file_size or 0) / (1024 * 1024)
        logger.info(f"File info: path={file_info.file_path}, size={file_size_mb:.1f}MB")
        
        if using_local_api:
            # Для локального API используем прямое скачивание
            logger.info("Using direct download from local Bot API")
            success = await download_file_from_bot_api(file_info.file_path, destination, BOT_TOKEN)
            
            # Если не получилось, пробуем через стандартный метод бота
            if not success:
                logger.info("Direct download failed, trying bot.download_file method")
                try:
                    await bot.download_file(file_info.file_path, destination)
                    actual_size_mb = destination.stat().st_size / (1024 * 1024)
                    logger.info(f"Downloaded via bot.download_file: {actual_size_mb:.1f}MB")
                    return True
                except Exception as e:
                    logger.error(f"bot.download_file also failed: {e}")
                    return False
            
            return success
        else:
            # Для стандартного API используем встроенный метод
            logger.info("Using standard bot.download_file")
            await bot.download_file(file_info.file_path, destination)
            actual_size_mb = destination.stat().st_size / (1024 * 1024)
            logger.info(f"Downloaded via standard API: {actual_size_mb:.1f}MB")
            return True
            
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False


async def send_to_api(file_path: Path, params: dict) -> Optional[str]:
    """Отправляет видео в API для обработки"""
    try:
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        logger.info(f"Sending to API: {file_path.name} ({file_size_mb:.1f}MB)")
        
        timeout = aiohttp.ClientTimeout(total=600)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = aiohttp.FormData()
            
            with open(file_path, 'rb') as f:
                data.add_field('file', f, filename=file_path.name)
            
            for key, value in params.items():
                data.add_field(key, str(value))
            
            url = f"{API_BASE_URL}/api/v1/process"
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    task_id = result.get('task_id')
                    logger.info(f"Task created: {task_id}")
                    return task_id
                else:
                    error = await resp.text()
                    logger.error(f"API error {resp.status}: {error}")
                    
    except Exception as e:
        logger.error(f"Send to API failed: {e}")
    
    return None


async def monitor_task(task_id: str, message: Message) -> dict:
    """Мониторит выполнение задачи с детальным прогрессом"""
    start_time = time.time()
    last_update_time = 0
    last_progress = -1
    error_count = 0
    max_errors = 3
    
    for attempt in range(120):  # 10 минут максимум
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{API_BASE_URL}/api/v1/status/{task_id}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        error_count = 0  # Сбрасываем счетчик ошибок
                    else:
                        error_count += 1
                        if error_count >= max_errors:
                            return {"status": "error", "message": f"API недоступен"}
                        await asyncio.sleep(5)
                        continue
                        
        except Exception as e:
            error_count += 1
            logger.error(f"Status check error: {e}")
            if error_count >= max_errors:
                return {"status": "error", "message": "Потеряна связь с API"}
            await asyncio.sleep(5)
            continue
        
        status = data.get('status', 'unknown')
        progress = data.get('progress', 0)
        message_text = data.get('message', '')
        
        # Обновляем сообщение только если прогресс изменился или прошло 10 секунд
        current_time = time.time()
        if progress != last_progress or (current_time - last_update_time) > 10:
            last_progress = progress
            last_update_time = current_time
            elapsed = int(current_time - start_time)
            elapsed_min = elapsed // 60
            elapsed_sec = elapsed % 60
            
            try:
                if status == 'processing':
                    await message.edit_text(
                        f"🔄 Обрабатываю видео...\n"
                        f"📊 Прогресс: {progress}%\n"
                        f"📝 {message_text}\n"
                        f"⏱️ Время: {elapsed_min}:{elapsed_sec:02d}"
                    )
                elif status == 'completed':
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
            except Exception:
                pass  # Игнорируем ошибки обновления сообщения
        
        await asyncio.sleep(5)
    
    await message.edit_text("⏰ Превышено время ожидания обработки (10 минут)")
    return {"status": "timeout"}


async def main():
    """Главная функция бота"""
    logger.info("Starting Shorts Maker Bot...")
    
    # Ждем API
    for i in range(30):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}/api/v1/health", timeout=5) as resp:
                    if resp.status == 200:
                        logger.info("Main API is ready")
                        break
        except:
            if i == 29:
                logger.error("Main API timeout")
                return
            await asyncio.sleep(2)
    
    # Создаем бота
    bot, using_local_api = await create_bot()
    dp = Dispatcher(storage=MemoryStorage())
    
    # Настройки
    max_file_size = 2_000_000_000 if using_local_api else 50_000_000
    max_size_str = "2GB" if using_local_api else "50MB"
    
    @dp.message(Command("start", "help"))
    async def cmd_start(message: Message, state: FSMContext):
        await message.answer(
            f"🎬 Привет! Я бот для создания шортсов из видео.\n\n"
            f"📊 Текущие настройки:\n"
            f"• Максимальный размер файла: {max_size_str}\n"
            f"• API: {'локальный (большие файлы)' if using_local_api else 'стандартный'}\n"
            f"• Формат результата: мобильные шортсы 9:16\n\n"
            f"📤 Просто отправьте мне видеофайл!"
        )
        await state.set_state(VideoProcessing.waiting_for_video)
    
    @dp.message(Command("status"))
    async def cmd_status(message: Message):
        statuses = {}
        
        # Проверяем основной API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}/api/v1/health", timeout=5) as resp:
                    statuses['main_api'] = '✅ работает' if resp.status == 200 else f'❌ ошибка {resp.status}'
        except:
            statuses['main_api'] = '❌ недоступен'
        
        # Проверяем Bot API
        statuses['bot_api'] = '✅ работает (2GB)' if using_local_api else '⚠️ стандартный (50MB)'
        
        await message.answer(
            f"📊 Статус системы:\n\n"
            f"Основной API: {statuses['main_api']}\n"
            f"Bot API: {statuses['bot_api']}\n"
            f"Макс. размер: {max_size_str}"
        )
    
    @dp.message(F.video, VideoProcessing.waiting_for_video)
    async def handle_video(message: Message, state: FSMContext):
        await process_media_file(message, state, message.video, "video")
    
    @dp.message(F.document, VideoProcessing.waiting_for_video)
    async def handle_document(message: Message, state: FSMContext):
        if not message.document.file_name:
            await message.answer("❌ Не удалось определить тип файла")
            return
            
        ext = Path(message.document.file_name).suffix.lower()
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        
        if ext not in video_extensions:
            await message.answer(f"❌ Неподдерживаемый формат: {ext}\nПоддерживаются: {', '.join(video_extensions)}")
            return
            
        await process_media_file(message, state, message.document, "document")
    
    async def process_media_file(message: Message, state: FSMContext, file_obj, file_type: str):
        """Обрабатывает видеофайл"""
        await state.set_state(VideoProcessing.processing)
        
        file_size = file_obj.file_size or 0
        file_size_mb = file_size / (1024 * 1024)
        
        logger.info(f"Processing {file_type}: {file_size_mb:.1f}MB")
        
        # Проверяем размер
        if file_size > max_file_size:
            await message.answer(
                f"❌ Файл слишком большой: {file_size_mb:.1f}MB\n"
                f"📊 Максимальный размер: {max_size_str}"
            )
            await state.set_state(VideoProcessing.waiting_for_video)
            return
        
        status_msg = await message.answer(
            f"📥 Скачиваю видео ({file_size_mb:.1f}MB)...\n"
            f"⏳ Это может занять некоторое время."
        )
        
        # Генерируем имя файла
        filename = getattr(file_obj, 'file_name', None) or f"video_{message.from_user.id}_{file_obj.file_id[:8]}.mp4"
        video_path = TEMP_DIR / filename
        
        # Скачиваем
        start_time = time.time()
        success = await download_file(bot, file_obj.file_id, video_path, using_local_api)
        download_time = time.time() - start_time
        
        if not success:
            await status_msg.edit_text(
                f"❌ Ошибка при скачивании файла.\n"
                f"💡 Попробуйте файл меньшего размера или повторите позже."
            )
            await state.set_state(VideoProcessing.waiting_for_video)
            return
        
        actual_size_mb = video_path.stat().st_size / (1024 * 1024)
        speed_mb = actual_size_mb / download_time if download_time > 0 else 0
        
        await status_msg.edit_text(
            f"✅ Файл скачан ({actual_size_mb:.1f}MB за {download_time:.1f}с, {speed_mb:.1f}MB/s)\n"
            f"🚀 Отправляю на обработку..."
        )
        
        # Отправляем в API
        params = {
            'algorithm': 'multi_shorts',
            'min_duration': 30,
            'max_duration': 90,
            'enable_subtitles': 'false',
            'mobile_scale_factor': 1.2
        }
        
        task_id = await send_to_api(video_path, params)
        
        if not task_id:
            await status_msg.edit_text("❌ Ошибка при отправке в API. Попробуйте позже.")
            video_path.unlink(missing_ok=True)
            await state.set_state(VideoProcessing.waiting_for_video)
            return
        
        # Мониторим прогресс
        await status_msg.edit_text(f"🔄 Обрабатываю видео...\n📋 Task ID: {task_id}")
        result = await monitor_task(task_id, status_msg)
        
        if result.get('status') == 'completed':
            # Отправляем ссылку на результат
            base_url = "http://localhost:8000" if not IS_DOCKER else API_BASE_URL
            download_url = f"{base_url}/api/v1/telegram/download-zip/{task_id}"
            
            await message.answer(
                f"🎉 Готово! Ваши шортсы готовы!\n\n"
                f"📦 Скачать архив:\n{download_url}\n\n"
                f"💡 Совет: откройте ссылку в браузере для скачивания"
            )
        elif result.get('status') == 'error':
            error_msg = result.get('error_message', 'Неизвестная ошибка')
            await message.answer(f"❌ Ошибка обработки:\n{error_msg}")
        else:
            await message.answer("⏰ Превышено время ожидания обработки")
        
        # Очистка
        video_path.unlink(missing_ok=True)
        await state.set_state(VideoProcessing.waiting_for_video)
    
    @dp.message(VideoProcessing.waiting_for_video)
    async def handle_other_messages(message: Message):
        await message.answer("📹 Отправьте видеофайл для обработки")
    
    logger.info(f"Bot ready! Max size: {max_size_str}")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())