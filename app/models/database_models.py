"""
Модели базы данных
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum

Base = declarative_base()


class TaskStatus(str, Enum):
    """Статусы задач"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ProcessingTask(Base):
    """Задачи обработки видео"""
    __tablename__ = "processing_tasks"
    
    # Основные поля
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(50), unique=True, index=True, nullable=False)
    
    # Статус и прогресс
    status = Column(String(20), default=TaskStatus.QUEUED, index=True)
    progress = Column(Integer, default=0)
    message = Column(Text, default="")
    error_message = Column(Text, nullable=True)
    
    # Файлы
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Путь к исходному файлу
    file_size = Column(Integer, nullable=True)
    
    # Параметры обработки
    algorithm = Column(String(50), default="multi_shorts")
    min_duration = Column(Integer, default=60)
    max_duration = Column(Integer, default=180)
    enable_subtitles = Column(Boolean, default=False)
    mobile_scale_factor = Column(Float, default=1.2)
    
    # Результаты
    segments_created = Column(Integer, default=0)
    result_files = Column(JSON, default=[])  # Список путей к готовым файлам
    processing_time = Column(Float, nullable=True)  # Время обработки в секундах
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Дополнительные поля
    ip_address = Column(String(45), nullable=True)  # IP пользователя
    user_agent = Column(Text, nullable=True)
    
    # Индексы для быстрых запросов
    __table_args__ = (
        Index('idx_status_created', 'status', 'created_at'),
        Index('idx_task_status', 'task_id', 'status'),
    )
    
    def to_dict(self):
        """Конвертация в словарь для API ответов"""
        return {
            'task_id': self.task_id,
            'status': self.status,
            'progress': self.progress,
            'message': self.message,
            'error_message': self.error_message,
            'result_files': self.result_files or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'segments_created': self.segments_created,
            'processing_time': self.processing_time,
            'original_filename': self.original_filename
        }


class ProcessingStats(Base):
    """Статистика обработки (опционально)"""
    __tablename__ = "processing_stats"
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Счетчики
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    total_segments_created = Column(Integer, default=0)
    
    # Размеры файлов
    total_input_size = Column(Integer, default=0)  # в байтах
    total_output_size = Column(Integer, default=0)  # в байтах
    
    # Время обработки
    avg_processing_time = Column(Float, default=0.0)
    max_processing_time = Column(Float, default=0.0)