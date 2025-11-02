"""
Сервис для обработки видео
Управляет задачами, статусами и результатами обработки
"""
import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.core.video_processor import VideoProcessor
from app.config.settings import settings
from app.models.schemas import TaskStatus, ProcessingRequest


class TaskManager:
    """Менеджер задач обработки видео"""
    
    def __init__(self):
        """Инициализация менеджера задач"""
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.video_processor = VideoProcessor()
        
        # Создаем папку для хранения статусов задач
        self.status_folder = Path("storage/temp/tasks")
        self.status_folder.mkdir(parents=True, exist_ok=True)
    
    def create_task(self, filename: str, request_params: ProcessingRequest) -> str:
        """
        Создает новую задачу обработки
        
        Args:
            filename: Имя загруженного файла
            request_params: Параметры обработки
            
        Returns:
            str: ID созданной задачи
        """
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        task_data = {
            'task_id': task_id,
            'status': TaskStatus.QUEUED,
            'filename': filename,
            'request_params': request_params.dict(),
            'progress': 0,
            'message': 'Задача добавлена в очередь',
            'result_files': [],
            'error_message': None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task_data
        self._save_task_status(task_id, task_data)
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает статус задачи
        
        Args:
            task_id: ID задачи
            
        Returns:
            Dict со статусом задачи или None если не найдена
        """
        if task_id in self.tasks:
            return self.tasks[task_id]
        
        # Пытаемся загрузить из файла
        return self._load_task_status(task_id)
    
    def update_task_status(self, 
                          task_id: str, 
                          status: TaskStatus = None,
                          progress: int = None,
                          message: str = None,
                          result_files: List[str] = None,
                          error_message: str = None):
        """
        Обновляет статус задачи
        
        Args:
            task_id: ID задачи
            status: Новый статус
            progress: Прогресс выполнения (0-100)
            message: Сообщение о статусе
            result_files: Список готовых файлов
            error_message: Сообщение об ошибке
        """
        if task_id not in self.tasks:
            return
        
        task_data = self.tasks[task_id]
        
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
        
        task_data['updated_at'] = datetime.now().isoformat()
        
        self._save_task_status(task_id, task_data)
    
    def _save_task_status(self, task_id: str, task_data: Dict[str, Any]):
        """Сохраняет статус задачи в файл"""
        try:
            status_file = self.status_folder / f"{task_id}.json"
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения статуса задачи {task_id}: {e}")
    
    def _load_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Загружает статус задачи из файла"""
        try:
            status_file = self.status_folder / f"{task_id}.json"
            if status_file.exists():
                with open(status_file, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)
                    self.tasks[task_id] = task_data
                    return task_data
        except Exception as e:
            print(f"Ошибка загрузки статуса задачи {task_id}: {e}")
        
        return None
    
    def cleanup_task_files(self, task_id: str):
        """
        Очищает временные файлы задачи
        
        Args:
            task_id: ID задачи
        """
        try:
            # Удаляем файл статуса
            status_file = self.status_folder / f"{task_id}.json"
            if status_file.exists():
                status_file.unlink()
            
            # Удаляем из памяти
            if task_id in self.tasks:
                del self.tasks[task_id]
                
        except Exception as e:
            print(f"Ошибка очистки файлов задачи {task_id}: {e}")


class VideoService:
    """Сервис для обработки видео"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self.task_manager = TaskManager()
    
    async def process_video_async(self, 
                                 video_path: Path, 
                                 task_id: str,
                                 request_params: ProcessingRequest) -> Dict[str, Any]:
        """
        Асинхронно обрабатывает видео
        
        Args:
            video_path: Путь к видеофайлу
            task_id: ID задачи
            request_params: Параметры обработки
            
        Returns:
            Dict с результатами обработки
        """
        try:
            # Обновляем статус - начинаем обработку
            self.task_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.PROCESSING,
                progress=10,
                message="Начинаем обработку видео..."
            )
            
            # Подготавливаем параметры для алгоритма
            algorithm_params = {
                'min_duration': request_params.min_duration,
                'max_duration': request_params.max_duration,
                'enable_subtitles': request_params.enable_subtitles,
                'mobile_scale_factor': request_params.mobile_scale_factor
            }
            
            # Создаем папку для результатов этой задачи
            output_folder = settings.output_path_obj / task_id
            output_folder.mkdir(parents=True, exist_ok=True)
            
            # Обновляем прогресс
            self.task_manager.update_task_status(
                task_id=task_id,
                progress=30,
                message="Анализируем видео и определяем точки нарезки..."
            )
            
            # Обрабатываем видео (это может занять время)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.task_manager.video_processor.process_video,
                video_path,
                output_folder,
                request_params.algorithm,
                **algorithm_params
            )
            
            if result['success']:
                # Формируем список файлов для скачивания
                result_files = []
                if 'result_files' in result:
                    for file_path in result['result_files']:
                        # Создаем относительный путь от output папки
                        rel_path = Path(file_path).relative_to(settings.output_path_obj)
                        download_url = f"/api/v1/download/{rel_path}"
                        result_files.append(download_url)
                
                # Обновляем статус - успешно завершено
                self.task_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    message=f"Обработка завершена успешно. Создано сегментов: {result.get('segments_created', 0)}",
                    result_files=result_files
                )
                
                return result
            else:
                # Ошибка обработки
                self.task_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.ERROR,
                    progress=0,
                    message="Ошибка при обработке видео",
                    error_message=result.get('error', 'Неизвестная ошибка')
                )
                
                return result
                
        except Exception as e:
            # Неожиданная ошибка
            error_message = f"Неожиданная ошибка: {str(e)}"
            
            self.task_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.ERROR,
                progress=0,
                message="Произошла неожиданная ошибка",
                error_message=error_message
            )
            
            return {
                'success': False,
                'error': error_message,
                'task_id': task_id
            }
    
    def create_processing_task(self, 
                             filename: str, 
                             request_params: ProcessingRequest) -> str:
        """
        Создает задачу обработки
        
        Args:
            filename: Имя загруженного файла
            request_params: Параметры обработки
            
        Returns:
            str: ID созданной задачи
        """
        return self.task_manager.create_task(filename, request_params)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает статус задачи
        
        Args:
            task_id: ID задачи
            
        Returns:
            Dict со статусом или None если не найдена
        """
        return self.task_manager.get_task_status(task_id)
    
    def start_processing(self, task_id: str, video_path: Path, request_params: ProcessingRequest):
        """
        Запускает асинхронную обработку видео
        
        Args:
            task_id: ID задачи
            video_path: Путь к видеофайлу
            request_params: Параметры обработки
        """
        # Это вызывается из BackgroundTasks, поэтому просто запускаем синхронно
        # Асинхронность уже обеспечивается через BackgroundTasks
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если loop уже запущен, создаем task
                loop.create_task(self.process_video_async(video_path, task_id, request_params))
            else:
                # Если нет loop, запускаем синхронно
                self._process_video_sync(video_path, task_id, request_params)
        except RuntimeError:
            # Если нет event loop, запускаем синхронно
            self._process_video_sync(video_path, task_id, request_params)
    
    def _process_video_sync(self, video_path: Path, task_id: str, request_params: ProcessingRequest):
        """
        Синхронная обработка видео (fallback)
        
        Args:
            video_path: Путь к видеофайлу
            task_id: ID задачи
            request_params: Параметры обработки
        """
        try:
            # Обновляем статус - начинаем обработку
            self.task_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.PROCESSING,
                progress=10,
                message="Начинаем обработку видео..."
            )
            
            # Подготавливаем параметры для алгоритма
            algorithm_params = {
                'min_duration': request_params.min_duration,
                'max_duration': request_params.max_duration,
                'enable_subtitles': request_params.enable_subtitles,
                'mobile_scale_factor': request_params.mobile_scale_factor
            }
            
            # Создаем папку для результатов этой задачи
            from app.config.settings import settings
            output_folder = settings.output_path_obj / task_id
            output_folder.mkdir(parents=True, exist_ok=True)
            
            # Обновляем прогресс
            self.task_manager.update_task_status(
                task_id=task_id,
                progress=30,
                message="Анализируем видео и определяем точки нарезки..."
            )
            
            # Обрабатываем видео синхронно
            result = self.task_manager.video_processor.process_video(
                video_path,
                output_folder,
                request_params.algorithm,
                **algorithm_params
            )
            
            if result['success']:
                # Формируем список файлов для скачивания
                result_files = []
                if 'result_files' in result:
                    for file_path in result['result_files']:
                        # Создаем относительный путь от output папки
                        rel_path = Path(file_path).relative_to(settings.output_path_obj)
                        download_url = f"/api/v1/download/{rel_path}"
                        result_files.append(download_url)
                
                # Обновляем статус - успешно завершено
                self.task_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    message=f"Обработка завершена успешно. Создано сегментов: {result.get('segments_created', 0)}",
                    result_files=result_files
                )
            else:
                # Ошибка обработки
                self.task_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.ERROR,
                    progress=0,
                    message="Ошибка при обработке видео",
                    error_message=result.get('error', 'Неизвестная ошибка')
                )
                
        except Exception as e:
            # Неожиданная ошибка
            error_message = f"Неожиданная ошибка: {str(e)}"
            
            self.task_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.ERROR,
                progress=0,
                message="Произошла неожиданная ошибка",
                error_message=error_message
            )


# Глобальный экземпляр сервиса
video_service = VideoService()