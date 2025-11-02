"""
Базовый процессор видео
Объединяет все компоненты для обработки видео
"""
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from app.config.settings import settings


class BaseVideoProcessor(ABC):
    """Базовый класс для всех алгоритмов обработки видео"""
    
    def __init__(self):
        """Инициализация базового процессора"""
        self.settings = settings
    
    @abstractmethod
    def process_video(self, video_path: Path, output_folder: Path, **kwargs) -> Dict[str, Any]:
        """
        Абстрактный метод для обработки видео
        
        Args:
            video_path: Путь к исходному видео
            output_folder: Папка для результатов
            **kwargs: Дополнительные параметры
            
        Returns:
            Dict с результатами обработки
        """
        pass
    
    def validate_video_file(self, video_path: Path) -> bool:
        """
        Проверяет валидность видеофайла
        
        Args:
            video_path: Путь к видеофайлу
            
        Returns:
            bool: True если файл валидный
        """
        if not video_path.exists():
            return False
        
        if video_path.suffix.lower() not in self.settings.video_extensions:
            return False
        
        if video_path.stat().st_size == 0:
            return False
        
        return True
    
    def check_ffmpeg(self) -> bool:
        """
        Проверяет наличие FFmpeg в системе
        
        Returns:
            bool: True если FFmpeg доступен
        """
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, text=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def get_video_info(self, video_path: Path) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о видеофайле
        
        Args:
            video_path: Путь к видеофайлу
            
        Returns:
            Dict с информацией о видео или None если ошибка
        """
        try:
            try:
                from moviepy.video.io.VideoFileClip import VideoFileClip
            except ImportError:
                from moviepy import VideoFileClip
                
            with VideoFileClip(str(video_path)) as clip:
                return {
                    'duration': clip.duration,
                    'width': clip.w,
                    'height': clip.h,
                    'fps': clip.fps,
                    'audio': clip.audio is not None
                }
        except Exception as e:
            print(f"Ошибка при получении информации о видео: {e}")
            return None


class VideoProcessor:
    """
    Главный процессор видео - координирует работу всех алгоритмов
    """
    
    def __init__(self):
        """Инициализация главного процессора"""
        self.algorithms = {}
        self._register_algorithms()
    
    def _register_algorithms(self):
        """Регистрирует доступные алгоритмы"""
        from app.algorithms.multi_shorts import MultiShortsAlgorithm
        
        self.algorithms = {
            'multi_shorts': MultiShortsAlgorithm
        }
    
    def get_available_algorithms(self) -> list:
        """
        Возвращает список доступных алгоритмов
        
        Returns:
            list: Список названий алгоритмов
        """
        return list(self.algorithms.keys())
    
    def create_algorithm(self, algorithm_name: str, **kwargs) -> BaseVideoProcessor:
        """
        Создает экземпляр алгоритма
        
        Args:
            algorithm_name: Название алгоритма
            **kwargs: Параметры для алгоритма
            
        Returns:
            Экземпляр алгоритма
            
        Raises:
            ValueError: Если алгоритм не найден
        """
        if algorithm_name not in self.algorithms:
            raise ValueError(f"Алгоритм '{algorithm_name}' не найден. Доступные: {list(self.algorithms.keys())}")
        
        algorithm_class = self.algorithms[algorithm_name]
        return algorithm_class(**kwargs)
    
    def process_video(self, 
                     video_path: Path, 
                     output_folder: Path,
                     algorithm: str = 'multi_shorts',
                     **algorithm_params) -> Dict[str, Any]:
        """
        Обрабатывает видео с указанным алгоритмом
        
        Args:
            video_path: Путь к исходному видео
            output_folder: Папка для результатов
            algorithm: Название алгоритма
            **algorithm_params: Параметры для алгоритма
            
        Returns:
            Dict с результатами обработки
        """
        try:
            # Создаем экземпляр алгоритма
            processor = self.create_algorithm(algorithm, **algorithm_params)
            
            # Проверяем валидность видео
            if not processor.validate_video_file(video_path):
                return {
                    'success': False,
                    'error': f'Невалидный видеофайл: {video_path}',
                    'algorithm_used': algorithm
                }
            
            # Проверяем FFmpeg
            if not processor.check_ffmpeg():
                return {
                    'success': False,
                    'error': 'FFmpeg не найден в системе',
                    'algorithm_used': algorithm
                }
            
            # Создаем выходную папку
            output_folder.mkdir(parents=True, exist_ok=True)
            
            # Обрабатываем видео
            result = processor.process_video(video_path, output_folder)
            result['algorithm_used'] = algorithm
            result['input_file'] = str(video_path)
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'algorithm_used': algorithm,
                'input_file': str(video_path)
            }