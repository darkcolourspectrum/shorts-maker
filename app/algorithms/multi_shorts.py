"""
Алгоритм Multi Shorts - нарезка одного видео на несколько шортсов
СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
"""
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any
from app.core.video_processor import BaseVideoProcessor
from app.core.content_analyzer import ContentAnalyzer
from app.core.segment_extractor import SegmentExtractor
from app.core.mobile_converter import MobileConverter
from app.core.subtitle_engine import SubtitleEngine


class MultiShortsAlgorithm(BaseVideoProcessor):
    """
    Алгоритм для создания множественных шортсов из одного видео
    ЛОГИКА СКОПИРОВАНА ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
    """
    
    def __init__(self, 
                 min_duration: int = 60,
                 max_duration: int = 180,
                 enable_subtitles: bool = False,
                 mobile_scale_factor: float = 1.2,
                 whisper_model: str = "base"):
        """
        Инициализация алгоритма
        
        Args:
            min_duration: Минимальная длительность сегмента в секундах
            max_duration: Максимальная длительность сегмента в секундах
            enable_subtitles: Включить генерацию субтитров
            mobile_scale_factor: Коэффициент увеличения основного видео
            whisper_model: Модель Whisper для субтитров
        """
        super().__init__()  # Вызываем конструктор базового класса
        
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.enable_subtitles = enable_subtitles
        self.mobile_scale_factor = mobile_scale_factor
        
        # Инициализируем компоненты
        self.content_analyzer = ContentAnalyzer(min_duration, max_duration)
        self.segment_extractor = SegmentExtractor()
        self.mobile_converter = MobileConverter(mobile_scale_factor)
        self.subtitle_engine = SubtitleEngine(whisper_model)
        
        # Поддерживаемые форматы видео (как в оригинальном скрипте)
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    
    def find_video_files(self, input_folder: Path) -> List[Path]:
        """
        Находит все видеофайлы в папке
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        """
        video_files = []
        for file_path in input_folder.rglob('*'):
            if file_path.suffix.lower() in self.video_extensions:
                video_files.append(file_path)
        return sorted(video_files)
    
    def check_ffmpeg(self) -> bool:
        """
        Проверяет наличие FFmpeg
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        """
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, text=True)
            print("FFmpeg найден")
            # Показываем версию для диагностики
            version_line = result.stdout.split('\n')[0] if result.stdout else "версия неизвестна"
            print(f"    {version_line}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("FFmpeg не найден! Установите FFmpeg и добавьте в PATH")
            print("    Для корректной работы субтитров нужна полная версия FFmpeg")
            print("    Инструкции: https://ffmpeg.org/download.html")
            return False
    
    def process_video(self, video_path: Path, output_folder: Path) -> Dict[str, Any]:
        """
        Обрабатывает одно видео
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        
        Args:
            video_path: Путь к исходному видео
            output_folder: Папка для сохранения результатов
            
        Returns:
            Dict с результатами обработки
        """
        print(f"\n Обработка: {video_path.name}")
        
        # Получаем точки нарезки
        segments = self.content_analyzer.get_optimal_cut_points(video_path)
        
        if not segments:
            print("  Не удалось найти подходящие сегменты")
            return {
                'success': False,
                'error': 'Не удалось найти подходящие сегменты',
                'segments_created': 0,
                'result_files': []
            }
        
        print(f"  Найдено {len(segments)} логических сегментов")
        
        # Создаем папку для этого видео
        video_output_folder = output_folder / video_path.stem
        video_output_folder.mkdir(exist_ok=True)
        
        successful_segments = 0
        result_files = []
        
        # Обрабатываем каждый сегмент
        for i, (start, end) in enumerate(segments, 1):
            duration = end - start
            segment_name = f"{video_path.stem}_part_{i:02d}_({duration:.0f}s).mp4"
            temp_segment_path = video_output_folder / f"temp_{segment_name}"
            final_segment_path = video_output_folder / segment_name
            
            print(f"    Сегмент {i}/{len(segments)}: {start:.1f}s - {end:.1f}s ({duration:.1f}s)")
            
            # Извлекаем сегмент
            if self.segment_extractor.extract_segment(video_path, start, end, temp_segment_path):
                print(f"    Видео сегмент извлечен")
                
                if temp_segment_path.exists():
                    # Генерируем субтитры если включены (пока отключено)
                    srt_content = ""
                    if self.enable_subtitles:
                        print(f"    Генерируем субтитры...")
                        srt_content = self.subtitle_engine.generate_subtitles(temp_segment_path)
                    
                    # Создаем мобильную версию
                    print(f"    Создаем мобильную версию...")
                    
                    if self.mobile_converter.convert_to_mobile_format(temp_segment_path, final_segment_path):
                        print(f"    {segment_name} готов (мобильная версия)!")
                        successful_segments += 1
                        result_files.append(str(final_segment_path))
                    else:
                        # Если мобильная версия не создалась, оставляем оригинальную
                        temp_segment_path.rename(final_segment_path)
                        print(f"    {segment_name} готов (оригинальная версия)")
                        successful_segments += 1
                        result_files.append(str(final_segment_path))
                    
                    # Удаляем временный файл
                    if temp_segment_path.exists():
                        temp_segment_path.unlink()
                else:
                    print(f"    Временный файл сегмента не найден")
            else:
                print(f"    Не удалось создать сегмент {i}")
        
        print(f"  Успешно создано сегментов: {successful_segments}/{len(segments)}")
        
        return {
            'success': successful_segments > 0,
            'segments_total': len(segments),
            'segments_created': successful_segments,
            'result_files': result_files,
            'output_folder': str(video_output_folder)
        }
    
    def process_multiple_videos(self, input_folder: Path, output_folder: Path) -> Dict[str, Any]:
        """
        Обрабатывает все видео в папке (как в оригинальном скрипте)
        
        Args:
            input_folder: Папка с исходными видео
            output_folder: Папка для результатов
            
        Returns:
            Dict с общими результатами
        """
        print("Запуск автоматического процессора видео для шортсов")
        print("=" * 60)
        
        # Проверяем наличие FFmpeg
        if not self.check_ffmpeg():
            return {
                'success': False,
                'error': 'FFmpeg не найден',
                'videos_processed': 0,
                'total_segments': 0
            }
        
        # Проверяем наличие видеофайлов
        video_files = self.find_video_files(input_folder)
        
        if not video_files:
            print(f" Видеофайлы не найдены в папке: {input_folder}")
            print(" Поместите видеофайлы в папку и попробуйте снова")
            
            return {
                'success': False,
                'error': f'Видеофайлы не найдены в папке: {input_folder}',
                'videos_processed': 0,
                'total_segments': 0
            }
        
        print(f" Найдено видеофайлов: {len(video_files)}")
        for video in video_files:
            print(f"   {video.name}")
        
        print(f"\n Настройки:")
        print(f"    Минимальная длительность сегмента: {self.min_duration} сек")
        print(f"    Максимальная длительность сегмента: {self.max_duration} сек")
        print(f"    Субтитры: {' включены (Whisper)' if self.enable_subtitles else ' отключены'}")
        
        # Обрабатываем каждое видео
        total_processed = 0
        total_segments = 0
        all_results = []
        
        for video_path in video_files:
            try:
                result = self.process_video(video_path, output_folder)
                if result['success']:
                    total_processed += 1
                    total_segments += result['segments_created']
                all_results.append(result)
            except Exception as e:
                print(f" Ошибка при обработке {video_path.name}: {e}")
                all_results.append({
                    'success': False,
                    'error': str(e),
                    'video_name': video_path.name
                })
                continue
        
        print("\n" + "=" * 60)
        print(f" Обработка завершена!")
        print(f" Обработано видео: {total_processed}/{len(video_files)}")
        print(f" Создано сегментов: {total_segments}")
        print(f" Результаты сохранены в: {output_folder}")
        
        return {
            'success': total_processed > 0,
            'videos_total': len(video_files),
            'videos_processed': total_processed,
            'total_segments': total_segments,
            'results': all_results,
            'output_folder': str(output_folder)
        }