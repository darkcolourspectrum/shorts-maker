"""
Конвертер в мобильный формат
СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
"""
import subprocess
from pathlib import Path

try:
    from moviepy.video.io.VideoFileClip import VideoFileClip
except ImportError:
    from moviepy import VideoFileClip


class MobileConverter:
    """Класс для конвертации видео в мобильный формат 9:16"""
    
    def __init__(self, mobile_scale_factor: float = 1.2):
        """
        Инициализация конвертера
        
        Args:
            mobile_scale_factor: Коэффициент увеличения основного видео (по умолчанию 1.2)
        """
        self.mobile_scale_factor = mobile_scale_factor
    
    def convert_to_mobile_format(self, input_path: Path, output_path: Path) -> bool:
        """
        Конвертирует видео в мобильный формат 9:16 с размытым фоном
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        
        Args:
            input_path: Путь к исходному видео
            output_path: Путь для сохранения результата
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        try:
            # Получаем информацию о видео
            with VideoFileClip(str(input_path)) as clip:
                original_width = clip.w
                original_height = clip.h
                original_ratio = original_width / original_height
            
            print(f"     Конвертируем в мобильный формат...")
            print(f"     Исходное разрешение: {original_width}x{original_height} ({original_ratio:.2f}:1)")
            
            # Целевое разрешение для мобильного (9:16)
            target_width = 1080
            target_height = 1920
            
            # СТРАТЕГИЯ: Основное видео по центру + размытый фон
            # 1. Масштабируем основное видео чуть больше чем по ширине для лучшей видимости
            main_scale_width = int(target_width * self.mobile_scale_factor)  # Увеличиваем на mobile_scale_factor
            main_scale_height = int(original_height * (main_scale_width / original_width))
            
            # 2. Позиция основного видео по центру экрана
            main_x = (target_width - main_scale_width) // 2  # Будет отрицательное - это нормально
            main_y = (target_height - main_scale_height) // 2
            
            # 3. Для фона: увеличиваем и размываем исходное видео
            # Масштабируем фон чтобы заполнил всю высоту (будет шире чем нужно, но нам так и надо)
            bg_scale_height = target_height
            bg_scale_width = int(original_width * (target_height / original_height))
            
            # Центрируем фон по горизонтали
            bg_x = (target_width - bg_scale_width) // 2
            
            print(f"     Основное видео: {main_scale_width}x{main_scale_height} в позиции ({main_x}, {main_y})")
            print(f"     Размытый фон: {bg_scale_width}x{bg_scale_height} в позиции ({bg_x}, 0)")
            
            # Создаем сложный фильтр:
            # [0:v] - исходное видео
            # Делаем фон: масштабируем на всю высоту, размываем, центрируем
            # Делаем основное: масштабируем больше чем экран для лучшей видимости, накладываем поверх фона
            filter_str = (
                f"[0:v]scale={bg_scale_width}:{bg_scale_height},boxblur=15:3,crop={target_width}:{target_height}:{abs(bg_x) if bg_x < 0 else 0}:0[bg];"
                f"[0:v]scale={main_scale_width}:{main_scale_height}[main];"
                f"[bg][main]overlay={main_x}:{main_y}"
            )
            
            print(f"     Применяем фильтр размытого фона...")
            
            # Выполняем конвертацию
            cmd = [
                'ffmpeg',
                '-i', str(input_path.absolute()),
                '-filter_complex', filter_str,
                '-c:a', 'copy',
                '-y',
                str(output_path.absolute())
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"     Мобильная версия создана с размытым фоном!")
                return True
            else:
                print(f"     Ошибка конвертации в мобильный формат:")
                if result.stderr:
                    error_lines = result.stderr.strip().split('\n')[-2:]
                    for line in error_lines:
                        if line.strip():
                            print(f"     {line}")
                return False
                
        except Exception as e:
            print(f"     Ошибка при конвертации в мобильный формат: {e}")
            return False