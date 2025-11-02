"""
API роуты для обработки видео
"""
import aiofiles
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional

from app.models.schemas import (
    ProcessingRequest, 
    ProcessingResponse, 
    TaskStatusResponse, 
    ErrorResponse,
    TaskStatus
)
from app.services.video_service import video_service
from app.config.settings import settings

router = APIRouter(prefix="/api/v1", tags=["video_processing"])


def validate_file(file: UploadFile) -> None:
    """
    Валидирует загруженный файл
    
    Args:
        file: Загруженный файл
        
    Raises:
        HTTPException: Если файл не прошел валидацию
    """
    # Проверяем размер файла
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"Файл слишком большой. Максимальный размер: {settings.max_file_size / 1024 / 1024:.0f} MB"
        )
    
    # Проверяем расширение файла
    if file.filename:
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in settings.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Неподдерживаемый формат файла: {file_extension}. "
                       f"Поддерживаемые форматы: {', '.join(settings.allowed_extensions)}"
            )


@router.post("/process", response_model=ProcessingResponse)
async def process_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    algorithm: str = "multi_shorts",
    min_duration: int = 60,
    max_duration: int = 180,
    enable_subtitles: bool = False,
    mobile_scale_factor: float = 1.2
):
    """
    Загружает видео и запускает обработку
    
    Args:
        background_tasks: Фоновые задачи FastAPI
        file: Загруженный видеофайл
        algorithm: Алгоритм обработки
        min_duration: Минимальная длительность сегмента в секундах
        max_duration: Максимальная длительность сегмента в секундах
        enable_subtitles: Включить генерацию субтитров
        mobile_scale_factor: Коэффициент увеличения основного видео
        
    Returns:
        ProcessingResponse: Ответ с ID задачи и статусом
    """
    try:
        # Валидируем файл
        validate_file(file)
        
        # Создаем параметры запроса
        request_params = ProcessingRequest(
            algorithm=algorithm,
            min_duration=min_duration,
            max_duration=max_duration,
            enable_subtitles=enable_subtitles,
            mobile_scale_factor=mobile_scale_factor
        )
        
        # Создаем задачу
        task_id = video_service.create_processing_task(file.filename, request_params)
        
        # Сохраняем загруженный файл
        upload_path = settings.upload_path_obj / file.filename
        async with aiofiles.open(upload_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Запускаем обработку в фоне
        background_tasks.add_task(
            video_service.start_processing,
            task_id,
            upload_path,
            request_params
        )
        
        return ProcessingResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            message="Задача добавлена в очередь на обработку"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Получает статус задачи обработки
    
    Args:
        task_id: ID задачи
        
    Returns:
        TaskStatusResponse: Статус задачи
    """
    task_status = video_service.get_task_status(task_id)
    
    if not task_status:
        raise HTTPException(
            status_code=404,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    return TaskStatusResponse(**task_status)


@router.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """
    Скачивает готовый файл
    
    Args:
        file_path: Относительный путь к файлу от output папки
        
    Returns:
        FileResponse: Файл для скачивания
    """
    try:
        # Строим полный путь к файлу
        full_path = settings.output_path_obj / file_path
        
        # Проверяем что файл существует
        if not full_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Файл не найден: {file_path}"
            )
        
        # Проверяем что путь находится в разрешенной папке (безопасность)
        try:
            full_path.resolve().relative_to(settings.output_path_obj.resolve())
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail="Доступ к файлу запрещен"
            )
        
        return FileResponse(
            path=str(full_path),
            filename=full_path.name,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при скачивании файла: {str(e)}"
        )


@router.get("/algorithms")
async def get_algorithms():
    """
    Возвращает список доступных алгоритмов обработки
    
    Returns:
        dict: Список алгоритмов с описаниями
    """
    return {
        "algorithms": [
            {
                "name": "multi_shorts",
                "title": "Множественные шортсы",
                "description": "Нарезает одно видео на несколько коротких сегментов с мобильной адаптацией",
                "parameters": {
                    "min_duration": "Минимальная длительность сегмента (30-300 сек)",
                    "max_duration": "Максимальная длительность сегмента (60-600 сек)",
                    "enable_subtitles": "Включить генерацию субтитров",
                    "mobile_scale_factor": "Коэффициент увеличения основного видео (1.0-2.0)"
                }
            }
        ]
    }


@router.get("/health")
async def health_check():
    """
    Проверка здоровья API
    
    Returns:
        dict: Статус сервиса
    """
    # Проверяем доступность FFmpeg
    from app.core.video_processor import VideoProcessor
    processor = VideoProcessor()
    temp_processor = processor.create_algorithm('multi_shorts')
    
    ffmpeg_available = temp_processor.check_ffmpeg()
    
    return {
        "status": "healthy",
        "ffmpeg_available": ffmpeg_available,
        "upload_path": str(settings.upload_path_obj),
        "output_path": str(settings.output_path_obj),
        "temp_path": str(settings.temp_path_obj)
    }


@router.delete("/cleanup/{task_id}")
async def cleanup_task(task_id: str):
    """
    Очищает файлы задачи (опционально)
    
    Args:
        task_id: ID задачи
        
    Returns:
        dict: Результат очистки
    """
    task_status = video_service.get_task_status(task_id)
    
    if not task_status:
        raise HTTPException(
            status_code=404,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    try:
        # Очищаем файлы задачи
        video_service.task_manager.cleanup_task_files(task_id)
        
        # Очищаем выходную папку задачи
        output_folder = settings.output_path_obj / task_id
        if output_folder.exists():
            import shutil
            shutil.rmtree(output_folder)
        
        return {
            "message": f"Файлы задачи {task_id} успешно очищены"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при очистке файлов: {str(e)}"
        )