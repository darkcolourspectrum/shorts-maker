"""
Извлекатель сегментов видео
СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
"""
import subprocess
from pathlib import Path


class SegmentExtractor:
    """Класс для извлечения сегментов видео"""
    
    def __init__(self):
        """Инициализация извлекателя"""
        pass
    
    def extract_segment(self, video_path: Path, start_time: float, end_time: float, output_path: Path) -> bool:
        """
        Извлекает сегмент видео
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        
        Args:
            video_path: Путь к исходному видео
            start_time: Начальное время в секундах
            end_time: Конечное время в секундах
            output_path: Путь для сохранения сегмента
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(start_time),
            '-t', str(end_time - start_time),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            str(output_path),
            '-y'  # Перезаписывать без вопросов
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"    Ошибка при создании сегмента: {e}")
            return False