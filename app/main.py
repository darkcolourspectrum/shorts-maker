"""
Главное FastAPI приложение для Shorts Maker API
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.api.routes.processing import router as processing_router
from app.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения
    """
    # Startup
    print("Запуск Shorts Maker API...")
    print(f"Папка загрузки: {settings.upload_path_obj}")
    print(f"Папка результатов: {settings.output_path_obj}")
    print(f"Временная папка: {settings.temp_path_obj}")
    
    # Создаем необходимые папки
    settings.upload_path_obj.mkdir(parents=True, exist_ok=True)
    settings.output_path_obj.mkdir(parents=True, exist_ok=True)
    settings.temp_path_obj.mkdir(parents=True, exist_ok=True)
    
    # Проверяем FFmpeg
    from app.core.video_processor import VideoProcessor
    processor = VideoProcessor()
    temp_processor = processor.create_algorithm('multi_shorts')
    
    if temp_processor.check_ffmpeg():
        print("FFmpeg найден и доступен")
    else:
        print("ПРЕДУПРЕЖДЕНИЕ: FFmpeg не найден! Обработка видео будет недоступна.")
    
    print("Shorts Maker API готов к работе!")
    
    yield
    
    # Shutdown
    print("Завершение работы Shorts Maker API...")


# Создаем FastAPI приложение
app = FastAPI(
    title="Shorts Maker API",
    description="""
    API для автоматической нарезки видео на шортсы
    
    ## Возможности:
    
    * **Загрузка видео** - поддержка популярных форматов (MP4, AVI, MKV, MOV и др.)
    * **Автоматическая нарезка** - умный алгоритм поиска логических точек разреза
    * **Мобильная адаптация** - конвертация в формат 9:16 с размытым фоном
    * **Субтитры** - автоматическая генерация субтитров (опционально)
    * **Асинхронная обработка** - мониторинг прогресса выполнения
    
    ## Алгоритмы:
    
    * **multi_shorts** - нарезка одного видео на несколько коротких сегментов
    
    ## Использование:
    
    1. Загрузите видео через `/api/v1/process`
    2. Получите task_id в ответе
    3. Отслеживайте прогресс через `/api/v1/status/{task_id}`
    4. Скачивайте готовые файлы через ссылки в результате
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(processing_router)


@app.get("/")
async def root():
    """
    Корневой эндпоинт - информация об API
    """
    return {
        "service": "Shorts Maker API",
        "version": "1.0.0",
        "description": "API для автоматической нарезки видео на шортсы",
        "endpoints": {
            "process": "/api/v1/process",
            "status": "/api/v1/status/{task_id}",
            "download": "/api/v1/download/{file_path}",
            "algorithms": "/api/v1/algorithms",
            "health": "/api/v1/health",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "settings": {
            "upload_path": str(settings.upload_path),
            "output_path": str(settings.output_path),
            "max_file_size_mb": settings.max_file_size // 1024 // 1024,
            "supported_formats": settings.allowed_extensions
        }
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """
    Обработчик HTTP исключений
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """
    Обработчик общих исключений
    """
    print(f"Неожиданная ошибка: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "Внутренняя ошибка сервера",
            "details": str(exc) if settings.debug else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    print("Запуск Shorts Maker API в режиме разработки...")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )