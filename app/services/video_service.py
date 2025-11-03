"""
Упрощенный сервис для обработки видео БЕЗ БД (для тестирования)
Использует JSON файлы как раньше
"""
import asyncio
import json
import os
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.core.video_processor import VideoProcessor
from app.config.settings import settings
from app.models.schemas import TaskStatus, ProcessingRequest


class TaskManager:
    """
    Менеджер задач - управляет статусами и файлами задач
    Использует JSON файлы (без БД)
    """
    
    def __init__(self):
        """Инициализация менеджера задач"""
        self.tasks_folder = settings.temp_path_obj / "tasks"
        self.tasks_folder.mkdir(parents=True, exist_ok=True)
        
    def _get_task_file(self, task_id: str) -> Path:
        """Получает путь к JSON файлу задачи"""
        return self.tasks_folder / f"{task_id}.json"
    
    def create_task(self, 
                   task_id: str, 
                   filename: str,
                   file_path: str,
                   algorithm: str = "multi_shorts",
                   **kwargs) -> Dict[str, Any]:
        """
        Создает новую задачу в JSON файле
        
        Args:
            task_id: Уникальный ID задачи
            filename: Оригинальное имя файла
            file_path: Путь к сохраненному файлу
            algorithm: Алгоритм обработки
            **kwargs: Дополнительные параметры
            
        Returns:
            Dict с данными созданной задачи
        """
        task_data = {
            'task_id': task_id,
            'status': TaskStatus.QUEUED,
            'progress': 0,
            'message': 'Задача создана',
            'filename': filename,
            'file_path': file_path,
            'algorithm': algorithm,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'result_files': [],
            'error_message': None,
            'segments_created': 0,
            'processing_time': None,
            **kwargs
        }
        
        # Сохраняем в JSON файл
        task_file = self._get_task_file(task_id)
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)
        
        return task_data
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает статус задачи из JSON файла
        
        Args:
            task_id: ID задачи
            
        Returns:
            Dict со статусом задачи или None
        """
        task_file = self._get_task_file(task_id)
        
        if not task_file.exists():
            return None
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка при чтении задачи {task_id}: {e}")
            return None
    
    def update_task_status(self,
                          task_id: str,
                          status: Optional[TaskStatus] = None,
                          progress: Optional[int] = None,
                          message: Optional[str] = None,
                          result_files: Optional[List[str]] = None,
                          error_message: Optional[str] = None,
                          segments_created: Optional[int] = None,
                          processing_time: Optional[float] = None):
        """
        Обновляет статус задачи в JSON файле
        
        Args:
            task_id: ID задачи
            status: Новый статус
            progress: Прогресс (0-100)
            message: Сообщение о статусе
            result_files: Список готовых файлов
            error_message: Сообщение об ошибке
            segments_created: Количество созданных сегментов
            processing_time: Время обработки в секундах
        """
        task_data = self.get_task_status(task_id)
        
        if not task_data:
            print(f"Задача {task_id} не найдена для обновления")
            return
        
        # Обновляем только переданные поля
        if status is not None:
            task_data['status'] = status
        if progress is not None:
            task_data['progress'] = progress
        if message is not None:
            task_data['message'] = message
        if result_files is not None:
            task_data['result_files'] = result_files
        if error_message is not None:
            task_data['error_message'] = error_message
        if segments_created is not None:
            task_data['segments_created'] = segments_created
        if processing_time is not None:
            task_data['processing_time'] = processing_time
        
        task_data['updated_at'] = datetime.now().isoformat()
        
        # Сохраняем обновленные данные
        task_file = self._get_task_file(task_id)
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)


class VideoService:
    """
    Основной сервис для обработки видео (упрощенная версия без БД)
    """
    
    def __init__(self):
        """Инициализация сервиса"""
        self.task_manager = TaskManager()
        self.video_processor = VideoProcessor()
    
    def create_processing_task(self, 
                              filename: str, 
                              file_path: Path,
                              request_params: ProcessingRequest,
                              ip_address: Optional[str] = None,
                              user_agent: Optional[str] = None) -> str:
        """
        Создает задачу обработки видео (синхронная версия)
        
        Args:
            filename: Имя загруженного файла
            file_path: Путь к сохраненному файлу
            request_params: Параметры обработки
            ip_address: IP адрес пользователя
            user_agent: User-Agent пользователя
            
        Returns:
            str: ID созданной задачи
        """
        # Генерируем уникальный ID задачи
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создаем задачу в JSON файле
        self.task_manager.create_task(
            task_id=task_id,
            filename=filename,
            file_path=str(file_path),
            algorithm=request_params.algorithm,
            min_duration=request_params.min_duration,
            max_duration=request_params.max_duration,
            enable_subtitles=request_params.enable_subtitles,
            mobile_scale_factor=request_params.mobile_scale_factor,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает статус задачи
        
        Args:
            task_id: ID задачи
            
        Returns:
            Dict со статусом задачи или None
        """
        return self.task_manager.get_task_status(task_id)
    
    async def process_video_async(self, 
                                 video_path: Path, 
                                 task_id: str,
                                 request_params: ProcessingRequest) -> Dict[str, Any]:
        """
        Асинхронно обрабатывает видео с обновлением статуса
        
        Args:
            video_path: Путь к видеофайлу
            task_id: ID задачи
            request_params: Параметры обработки
            
        Returns:
            Dict с результатами обработки
        """
        start_time = time.time()
        
        try:
            # Обновляем статус - начинаем обработку
            self.task_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.PROCESSING,
                progress=10,
                message="Начинаем анализ видео..."
            )
            
            # Создаем папку для результатов этой задачи
            output_folder = settings.output_path_obj / task_id
            output_folder.mkdir(parents=True, exist_ok=True)
            
            # Подготавливаем параметры алгоритма
            algorithm_params = {
                'min_duration': request_params.min_duration,
                'max_duration': request_params.max_duration,
                'enable_subtitles': request_params.enable_subtitles,
                'mobile_scale_factor': request_params.mobile_scale_factor
            }
            
            # Прогресс: анализ видео
            self.task_manager.update_task_status(
                task_id=task_id,
                progress=30,
                message="Определяем оптимальные точки нарезки..."
            )
            
            # Обрабатываем видео (запускаем в thread pool)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._process_video_sync,
                video_path,
                output_folder,
                request_params.algorithm,
                algorithm_params,
                task_id
            )
            
            processing_time = time.time() - start_time
            
            if result['success']:
                # Формируем список файлов для скачивания
                result_files = []
                if 'result_files' in result:
                    for file_path in result['result_files']:
                        # Создаем относительный путь для API
                        rel_path = Path(file_path).relative_to(settings.output_path_obj)
                        download_url = f"/api/v1/download/{rel_path}"
                        result_files.append(download_url)
                
                # Обновляем статус - успешно завершено
                self.task_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    message=f"Обработка завершена! Создано сегментов: {result.get('segments_created', 0)}",
                    result_files=result_files,
                    segments_created=result.get('segments_created', 0),
                    processing_time=processing_time
                )
                
                return result
            else:
                # Ошибка при обработке
                self.task_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.ERROR,
                    progress=0,
                    message="Ошибка при обработке видео",
                    error_message=result.get('error', 'Неизвестная ошибка'),
                    processing_time=processing_time
                )
                
                return result
                
        except Exception as e:
            # Неожиданная ошибка
            processing_time = time.time() - start_time
            error_message = f"Неожиданная ошибка: {str(e)}"
            
            self.task_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.ERROR,
                progress=0,
                message="Произошла неожиданная ошибка при обработке",
                error_message=error_message,
                processing_time=processing_time
            )
            
            return {
                'success': False,
                'error': error_message,
                'task_id': task_id
            }
    
    def _process_video_sync(self, 
                           video_path: Path, 
                           output_folder: Path, 
                           algorithm: str,
                           algorithm_params: Dict[str, Any],
                           task_id: str) -> Dict[str, Any]:
        """
        Синхронная обработка видео
        
        Args:
            video_path: Путь к видеофайлу
            output_folder: Папка для результатов
            algorithm: Алгоритм обработки
            algorithm_params: Параметры алгоритма
            task_id: ID задачи для логирования
            
        Returns:
            Dict с результатами обработки
        """
        try:
            print(f"Начинаем обработку видео для задачи {task_id}")
            
            # Используем video_processor для обработки
            result = self.video_processor.process_video(
                video_path=video_path,
                output_folder=output_folder,
                algorithm=algorithm,
                **algorithm_params
            )
            
            print(f"Обработка задачи {task_id} завершена: {result.get('success', False)}")
            return result
            
        except Exception as e:
            error_msg = f"Ошибка при синхронной обработке: {str(e)}"
            print(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'task_id': task_id
            }
    
    def start_processing(self, task_id: str, video_path: Path, request_params: ProcessingRequest):
        """
        Запускает асинхронную обработку видео в фоне
        
        Args:
            task_id: ID задачи
            video_path: Путь к видеофайлу
            request_params: Параметры обработки
        """
        # Используем правильный способ запуска асинхронной функции в background task
        import asyncio
        try:
            # Пытаемся получить текущий event loop
            loop = asyncio.get_event_loop()
            # Создаем задачу в текущем loop
            loop.create_task(self.process_video_async(video_path, task_id, request_params))
        except RuntimeError:
            # Если нет event loop, создаем новый
            asyncio.run(self.process_video_async(video_path, task_id, request_params))


# Глобальный экземпляр сервиса
video_service = VideoService()