"""
Pydantic модели для API
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum


class TaskStatus(str, Enum):
    """Статусы задач обработки"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ProcessingAlgorithm(str, Enum):
    """Доступные алгоритмы обработки"""
    MULTI_SHORTS = "multi_shorts"
    # Будущие алгоритмы можно добавить сюда


class ProcessingRequest(BaseModel):
    """Запрос на обработку видео"""
    algorithm: ProcessingAlgorithm = ProcessingAlgorithm.MULTI_SHORTS
    min_duration: int = Field(default=60, ge=30, le=300, description="Минимальная длительность сегмента в секундах")
    max_duration: int = Field(default=180, ge=60, le=600, description="Максимальная длительность сегмента в секундах")
    enable_subtitles: bool = Field(default=False, description="Включить генерацию субтитров")
    mobile_scale_factor: float = Field(default=1.2, ge=1.0, le=2.0, description="Коэффициент увеличения основного видео")
    
    class Config:
        json_schema_extra = {
            "example": {
                "algorithm": "multi_shorts",
                "min_duration": 60,
                "max_duration": 180,
                "enable_subtitles": False,
                "mobile_scale_factor": 1.2
            }
        }


class ProcessingResponse(BaseModel):
    """Ответ на запрос обработки"""
    task_id: str = Field(description="Уникальный идентификатор задачи")
    status: TaskStatus = Field(description="Статус задачи")
    message: str = Field(description="Сообщение о статусе")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_123456789",
                "status": "queued",
                "message": "Задача добавлена в очередь на обработку"
            }
        }


class TaskStatusResponse(BaseModel):
    """Информация о статусе задачи"""
    task_id: str = Field(description="Идентификатор задачи")
    status: TaskStatus = Field(description="Текущий статус")
    progress: int = Field(default=0, ge=0, le=100, description="Прогресс выполнения в процентах")
    message: str = Field(description="Подробное сообщение")
    result_files: List[str] = Field(default=[], description="Список ссылок на готовые файлы")
    error_message: Optional[str] = Field(default=None, description="Сообщение об ошибке, если есть")
    created_at: str = Field(description="Время создания задачи")
    updated_at: str = Field(description="Время последнего обновления")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_123456789",
                "status": "completed",
                "progress": 100,
                "message": "Обработка завершена успешно",
                "result_files": [
                    "/api/v1/download/task_123456789/video_part_01_120s.mp4",
                    "/api/v1/download/task_123456789/video_part_02_95s.mp4"
                ],
                "error_message": None,
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:05:30Z"
            }
        }


class ErrorResponse(BaseModel):
    """Ответ с ошибкой"""
    error: str = Field(description="Тип ошибки")
    message: str = Field(description="Подробное сообщение об ошибке")
    details: Optional[dict] = Field(default=None, description="Дополнительные детали ошибки")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Неподдерживаемый формат файла",
                "details": {
                    "file_extension": ".txt",
                    "allowed_extensions": [".mp4", ".avi", ".mkv"]
                }
            }
        }


class VideoInfo(BaseModel):
    """Информация о видеофайле"""
    filename: str = Field(description="Имя файла")
    size: int = Field(description="Размер файла в байтах")
    duration: Optional[float] = Field(default=None, description="Длительность в секундах")
    width: Optional[int] = Field(default=None, description="Ширина видео")
    height: Optional[int] = Field(default=None, description="Высота видео")
    format: Optional[str] = Field(default=None, description="Формат видео")


class SegmentInfo(BaseModel):
    """Информация о сегменте видео"""
    segment_number: int = Field(description="Номер сегмента")
    start_time: float = Field(description="Начальное время в секундах")
    end_time: float = Field(description="Конечное время в секундах")
    duration: float = Field(description="Длительность сегмента в секундах")
    filename: str = Field(description="Имя выходного файла")
    file_size: Optional[int] = Field(default=None, description="Размер файла в байтах")


class ProcessingResult(BaseModel):
    """Результат обработки видео"""
    task_id: str = Field(description="Идентификатор задачи")
    original_video: VideoInfo = Field(description="Информация об исходном видео")
    algorithm_used: ProcessingAlgorithm = Field(description="Использованный алгоритм")
    segments_created: int = Field(description="Количество созданных сегментов")
    segments: List[SegmentInfo] = Field(description="Информация о сегментах")
    processing_time: float = Field(description="Время обработки в секундах")
    subtitles_enabled: bool = Field(description="Были ли включены субтитры")
    mobile_converted: bool = Field(description="Была ли выполнена мобильная конвертация")