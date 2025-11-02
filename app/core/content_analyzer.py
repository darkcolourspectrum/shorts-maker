"""
Анализатор контента видео
СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
"""
import subprocess
from pathlib import Path
from typing import List, Tuple

try:
    from moviepy.video.io.VideoFileClip import VideoFileClip
except ImportError:
    from moviepy import VideoFileClip


class ContentAnalyzer:
    """Анализатор контента видео для определения точек нарезки"""
    
    def __init__(self, min_duration: int = 60, max_duration: int = 180):
        """
        Инициализация анализатора
        
        Args:
            min_duration: Минимальная длительность сегмента в секундах
            max_duration: Максимальная длительность сегмента в секундах
        """
        self.min_duration = min_duration
        self.max_duration = max_duration
    
    def detect_scene_changes(self, video_path: Path) -> List[float]:
        """
        Определяет моменты смены сцен с помощью FFmpeg
        Возвращает список временных меток в секундах
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        """
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-filter:v', 'select="gt(scene,0.3)",showinfo',
            '-f', 'null',
            '-y',
            '-'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            scene_times = []
            
            # Ищем в stderr где FFmpeg выводит информацию
            output_text = result.stderr if result.stderr else result.stdout
            
            for line in output_text.split('\n'):
                if 'pts_time:' in line:
                    try:
                        time_str = line.split('pts_time:')[1].split()[0]
                        scene_times.append(float(time_str))
                    except (IndexError, ValueError):
                        continue
            
            return sorted(scene_times)
        except Exception as e:
            print(f"Ошибка при определении сцен: {e}")
            return []
    
    def detect_silence_pauses(self, video_path: Path, silence_threshold: float = -30) -> List[float]:
        """
        Определяет паузы в аудио (тишина) для логических разрывов
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        """
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-af', f'silencedetect=noise={silence_threshold}dB:duration=1',
            '-f', 'null',
            '-y',
            '-'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            silence_times = []
            
            # Ищем в stderr где FFmpeg выводит информацию
            output_text = result.stderr if result.stderr else result.stdout
            
            for line in output_text.split('\n'):
                if 'silence_start:' in line:
                    try:
                        time_str = line.split('silence_start:')[1].split()[0]
                        silence_times.append(float(time_str))
                    except (IndexError, ValueError):
                        continue
            
            return sorted(silence_times)
        except Exception as e:
            print(f"Ошибка при определении пауз: {e}")
            return []
    
    def get_optimal_cut_points(self, video_path: Path) -> List[Tuple[float, float]]:
        """
        Определяет оптимальные точки нарезки на основе сцен и пауз
        Возвращает список кортежей (начало, конец) в секундах
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        """
        print("   Анализируем видео для поиска логических точек разреза...")
        
        # Получаем длительность видео
        try:
            with VideoFileClip(str(video_path)) as clip:
                duration = clip.duration
        except Exception as e:
            print(f"  Ошибка при получении длительности видео: {e}")
            return []
        
        print(f"  Длительность видео: {duration:.1f} секунд")
        
        # Получаем точки смены сцен и пауз
        scene_changes = self.detect_scene_changes(video_path)
        silence_pauses = self.detect_silence_pauses(video_path)
        
        print(f"  Найдено смен сцен: {len(scene_changes)}")
        print(f"  Найдено пауз: {len(silence_pauses)}")
        
        # Объединяем и сортируем все потенциальные точки разреза
        all_cuts = sorted(set(scene_changes + silence_pauses + [0, duration]))
        
        # Формируем сегменты оптимальной длины
        segments = []
        current_start = 0
        
        for i, cut_point in enumerate(all_cuts[1:], 1):
            segment_duration = cut_point - current_start
            
            # Если сегмент слишком короткий, продолжаем
            if segment_duration < self.min_duration:
                continue
            
            # Если сегмент слишком длинный, ищем промежуточную точку
            if segment_duration > self.max_duration:
                # Ищем ближайшую точку разреза в пределах max_duration
                target_end = current_start + self.max_duration
                best_cut = current_start + self.max_duration
                
                for potential_cut in all_cuts:
                    if current_start < potential_cut <= target_end:
                        if abs(potential_cut - target_end) < abs(best_cut - target_end):
                            best_cut = potential_cut
                
                segments.append((current_start, best_cut))
                current_start = best_cut
            else:
                segments.append((current_start, cut_point))
                current_start = cut_point
        
        # Добавляем последний сегмент если он достаточно длинный
        if duration - current_start >= self.min_duration:
            segments.append((current_start, duration))
        
        return segments