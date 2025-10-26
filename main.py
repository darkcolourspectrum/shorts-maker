#!/usr/bin/env python3
"""
Автоматический процессор видео для создания шортсов
Просто положите видео в папку 'input_videos' и запустите скрипт
"""

import os
import subprocess
import json
from pathlib import Path
from typing import List, Tuple
import numpy as np

# Используем рабочий импорт
from moviepy import VideoFileClip
print("✅ moviepy импортирован успешно")

# Пробуем импорт whisper
try:
    import whisper
    print("✅ whisper импортирован успешно")
except ImportError:
    print("⚠️ whisper не найден, субтитры будут отключены")
    whisper = None

class VideoShortsProcessor:
    def __init__(self):
        """
        Инициализация процессора с автоматическими папками
        """
        # Определяем папки относительно скрипта
        self.project_root = Path(__file__).parent
        self.input_folder = self.project_root / "input_videos"
        self.output_folder = self.project_root / "output_shorts"
        
        # Настройки по умолчанию
        self.min_duration = 60  # 1 минута
        self.max_duration = 180  # 3 минуты
        
        # Создаем папки если их нет
        self.input_folder.mkdir(exist_ok=True)
        self.output_folder.mkdir(exist_ok=True)
        
        print(f"📁 Папка для видео: {self.input_folder}")
        print(f"📁 Папка для шортсов: {self.output_folder}")
        
        # Загружаем модель Whisper для субтитров
        print("🤖 Модель Whisper отключена для быстрого тестирования...")
        self.whisper_model = None  # ВРЕМЕННО ОТКЛЮЧЕНО
        # try:
        #     self.whisper_model = whisper.load_model("base")
        #     print("✅ Модель Whisper загружена")
        # except Exception as e:
        #     print(f"⚠️ Ошибка загрузки Whisper: {e}")
        #     print("📝 Субтитры будут отключены")
        #     self.whisper_model = None
        
        # Поддерживаемые форматы видео
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    
    def find_video_files(self) -> List[Path]:
        """Находит все видеофайлы в папке input_videos"""
        video_files = []
        for file_path in self.input_folder.rglob('*'):
            if file_path.suffix.lower() in self.video_extensions:
                video_files.append(file_path)
        return sorted(video_files)
    
    def detect_scene_changes(self, video_path: Path) -> List[float]:
        """
        Определяет моменты смены сцен с помощью FFmpeg
        Возвращает список временных меток в секундах
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
            print(f"⚠️ Ошибка при определении сцен: {e}")
            return []
    
    def detect_silence_pauses(self, video_path: Path, silence_threshold: float = -30) -> List[float]:
        """
        Определяет паузы в аудио (тишина) для логических разрывов
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
            print(f"⚠️ Ошибка при определении пауз: {e}")
            return []
    
    def get_optimal_cut_points(self, video_path: Path) -> List[Tuple[float, float]]:
        """
        Определяет оптимальные точки нарезки на основе сцен и пауз
        Возвращает список кортежей (начало, конец) в секундах
        """
        print("  🔍 Анализируем видео для поиска логических точек разреза...")
        
        # Получаем длительность видео
        try:
            with VideoFileClip(str(video_path)) as clip:
                duration = clip.duration
        except Exception as e:
            print(f"  ❌ Ошибка при получении длительности видео: {e}")
            return []
        
        print(f"  📏 Длительность видео: {duration:.1f} секунд")
        
        # Получаем точки смены сцен и пауз
        scene_changes = self.detect_scene_changes(video_path)
        silence_pauses = self.detect_silence_pauses(video_path)
        
        print(f"  🎬 Найдено смен сцен: {len(scene_changes)}")
        print(f"  🔇 Найдено пауз: {len(silence_pauses)}")
        
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
    
    def extract_segment(self, video_path: Path, start_time: float, end_time: float, output_path: Path):
        """Извлекает сегмент видео"""
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
            print(f"    ❌ Ошибка при создании сегмента: {e}")
            return False
    
    def generate_subtitles(self, video_path: Path) -> str:
        """Генерирует субтитры для видео используя Whisper"""
        if not self.whisper_model:
            return ""
        
        try:
            result = self.whisper_model.transcribe(str(video_path))
            
            # Формируем SRT субтитры
            srt_content = ""
            for i, segment in enumerate(result["segments"], 1):
                start_time = self.seconds_to_srt_time(segment["start"])
                end_time = self.seconds_to_srt_time(segment["end"])
                text = segment["text"].strip()
                
                srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
            
            return srt_content
        except Exception as e:
            print(f"    ⚠️ Ошибка при генерации субтитров: {e}")
            return ""
    
    def seconds_to_srt_time(self, seconds: float) -> str:
        """Конвертирует секунды в формат времени SRT"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def convert_to_mobile_format(self, input_path: Path, output_path: Path):
        """Конвертирует видео в мобильный формат 9:16 с размытым фоном"""
        try:
            # Получаем информацию о видео
            with VideoFileClip(str(input_path)) as clip:
                original_width = clip.w
                original_height = clip.h
                original_ratio = original_width / original_height
            
            print(f"    📱 Конвертируем в мобильный формат...")
            print(f"    📏 Исходное разрешение: {original_width}x{original_height} ({original_ratio:.2f}:1)")
            
            # Целевое разрешение для мобильного (9:16)
            target_width = 1080
            target_height = 1920
            
            # СТРАТЕГИЯ: Основное видео по центру + размытый фон
            # 1. Масштабируем основное видео чуть больше чем по ширине для лучшей видимости
            main_scale_width = int(target_width * 1.2)  # Увеличиваем на 20% = 1296px вместо 1080px
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
            
            print(f"    🎯 Основное видео: {main_scale_width}x{main_scale_height} в позиции ({main_x}, {main_y})")
            print(f"    🌫️ Размытый фон: {bg_scale_width}x{bg_scale_height} в позиции ({bg_x}, 0)")
            
            # Создаем сложный фильтр:
            # [0:v] - исходное видео
            # Делаем фон: масштабируем на всю высоту, размываем, центрируем
            # Делаем основное: масштабируем больше чем экран для лучшей видимости, накладываем поверх фона
            filter_str = (
                f"[0:v]scale={bg_scale_width}:{bg_scale_height},boxblur=15:3,crop={target_width}:{target_height}:{abs(bg_x) if bg_x < 0 else 0}:0[bg];"
                f"[0:v]scale={main_scale_width}:{main_scale_height}[main];"
                f"[bg][main]overlay={main_x}:{main_y}"
            )
            
            print(f"    🔧 Применяем фильтр размытого фона...")
            
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
                print(f"    ✅ Мобильная версия создана с размытым фоном!")
                return True
            else:
                print(f"    ❌ Ошибка конвертации в мобильный формат:")
                if result.stderr:
                    error_lines = result.stderr.strip().split('\n')[-2:]
                    for line in error_lines:
                        if line.strip():
                            print(f"    ⚠️ {line}")
                return False
                
        except Exception as e:
            print(f"    ❌ Ошибка при конвертации в мобильный формат: {e}")
            return False

    def add_subtitles_with_drawtext(self, video_path: Path, srt_content: str, output_path: Path):
        """Альтернативный способ - используем drawtext для каждой строки субтитров"""
        try:
            # Парсим SRT контент
            subtitle_entries = self.parse_srt_content(srt_content)
            
            if not subtitle_entries:
                print("    ⚠️ Не удалось распарсить субтитры для drawtext")
                return False
            
            print(f"    🎯 Используем drawtext для {len(subtitle_entries)} фрагментов субтитров")
            
            # Создаем фильтр drawtext для каждого субтитра
            drawtext_filters = []
            for entry in subtitle_entries:
                start_sec = entry['start']
                end_sec = entry['end'] 
                text = entry['text'].replace("'", "\\'").replace(":", "\\:")
                
                # Создаем фильтр для этого времени - ОПТИМАЛЬНЫЙ РАЗМЕР
                filter_str = f"drawtext=fontfile=C\\\\:/Windows/Fonts/arial.ttf:text='{text}':fontcolor=white:fontsize=28:box=1:boxcolor=black@0.7:boxborderw=6:x=(w-text_w)/2:y=h-th-30:enable='between(t,{start_sec},{end_sec})'"
                drawtext_filters.append(filter_str)
            
            # Объединяем все фильтры
            combined_filter = ','.join(drawtext_filters)
            
            # Выполняем команду
            video_path_str = str(video_path.absolute())
            output_path_str = str(output_path.absolute())
            
            cmd = [
                'ffmpeg',
                '-i', video_path_str,
                '-vf', combined_filter,
                '-c:a', 'copy',
                '-y',
                output_path_str
            ]
            
            print(f"    🔧 Способ 2: Используем drawtext...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"    ✅ Субтитры встроены через drawtext!")
                return True
            else:
                print(f"    ❌ Drawtext тоже не сработал")
                return False
                
        except Exception as e:
            print(f"    ❌ Ошибка в drawtext методе: {e}")
            return False
    
    def parse_srt_content(self, srt_content: str) -> List[dict]:
        """Парсит SRT контент в список словарей с временными метками"""
        entries = []
        blocks = srt_content.strip().split('\n\n')
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                try:
                    # Парсим строку времени (например: 00:00:01,500 --> 00:00:05,000)
                    time_line = lines[1]
                    if ' --> ' in time_line:
                        start_str, end_str = time_line.split(' --> ')
                        start_sec = self.srt_time_to_seconds(start_str.strip())
                        end_sec = self.srt_time_to_seconds(end_str.strip())
                        
                        # Объединяем текстовые строки
                        text = ' '.join(lines[2:])
                        
                        entries.append({
                            'start': start_sec,
                            'end': end_sec,
                            'text': text
                        })
                except Exception as e:
                    print(f"    ⚠️ Ошибка парсинга блока: {e}")
                    continue
        
        return entries
    
    def srt_time_to_seconds(self, time_str: str) -> float:
        """Конвертирует время SRT (00:00:01,500) в секунды"""
        try:
            # Формат: HH:MM:SS,mmm
            time_part, ms_part = time_str.split(',')
            hours, minutes, seconds = map(int, time_part.split(':'))
            milliseconds = int(ms_part)
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
            return total_seconds
        except Exception:
            return 0.0

    def add_subtitles_to_video(self, video_path: Path, srt_content: str, output_path: Path):
        """Добавляет субтитры к видео - РАБОЧАЯ ВЕРСИЯ С ПРЯМЫМ ПУТЕМ К ШРИФТУ"""
        if not srt_content.strip():
            print("    ⚠️ Пустые субтитры, сохраняем видео без них")
            import shutil
            shutil.copy2(video_path, output_path)
            return True
        
        # Сохраняем субтитры во временный файл
        srt_path = output_path.parent / f"temp_{output_path.stem}.srt"
        
        try:
            # Записываем SRT файл
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            print(f"    📝 Временный SRT файл создан: {srt_path.name}")
            
            # Проверяем что файл создался
            if not srt_path.exists():
                print(f"    ❌ Не удалось создать файл субтитров")
                return False
            
            # Используем абсолютные пути
            video_path_str = str(video_path.absolute())
            output_path_str = str(output_path.absolute())
            srt_path_str = str(srt_path.absolute()).replace('\\', '/')
            
            # СПОСОБ 1: Используем subtitles фильтр с прямым путем к шрифту
            cmd1 = [
                'ffmpeg',
                '-i', video_path_str,
                '-vf', f"subtitles={srt_path_str}:fontfile=C\\:/Windows/Fonts/arial.ttf:fontsize=24:fontcolor=white:outline=1:outlinecolor=black",
                '-c:a', 'copy',
                '-y',
                output_path_str
            ]
            
            print(f"    🔧 Способ 1: Встраиваем субтитры с прямым путем к шрифту...")
            print(f"    📄 Команда: ffmpeg -i {video_path.name} [subtitles+font] {output_path.name}")
            
            result1 = subprocess.run(cmd1, capture_output=True, text=True)
            
            if result1.returncode == 0:
                print(f"    ✅ Субтитры успешно встроены!")
                return True
            else:
                print(f"    ⚠️ Способ 1 не сработал, пробуем drawtext...")
                
                # СПОСОБ 2: Используем drawtext - парсим SRT и накладываем каждую строку
                if self.add_subtitles_with_drawtext(video_path, srt_content, output_path):
                    return True
                
                # СПОСОБ 3: Упрощенные субтитры без шрифта
                cmd3 = [
                    'ffmpeg',
                    '-i', video_path_str,
                    '-vf', f"subtitles={srt_path_str}",
                    '-c:a', 'copy',
                    '-y',
                    output_path_str
                ]
                
                print(f"    🔧 Способ 3: Простые субтитры без шрифта...")
                result3 = subprocess.run(cmd3, capture_output=True, text=True)
                
                if result3.returncode == 0:
                    print(f"    ✅ Субтитры встроены (простой вариант)")
                    return True
                else:
                    print(f"    ❌ Все способы не сработали, сохраняем без субтитров")
                    import shutil
                    shutil.copy2(video_path, output_path)
                    return True
                
        except Exception as e:
            print(f"    ❌ Общая ошибка при обработке субтитров: {e}")
            try:
                import shutil
                shutil.copy2(video_path, output_path)
                print(f"    📄 Видео сохранено без субтитров")
                return True
            except Exception as copy_error:
                print(f"    ❌ Ошибка при копировании видео: {copy_error}")
                return False
        finally:
            # Убираем временный SRT файл
            if srt_path.exists():
                try:
                    srt_path.unlink()
                except:
                    pass
    
    def process_video(self, video_path: Path):
        """Обрабатывает одно видео"""
        print(f"\n🎬 Обработка: {video_path.name}")
        
        # Получаем точки нарезки
        segments = self.get_optimal_cut_points(video_path)
        
        if not segments:
            print("  ❌ Не удалось найти подходящие сегменты")
            return
        
        print(f"  ✅ Найдено {len(segments)} логических сегментов")
        
        # Создаем папку для этого видео
        video_output_folder = self.output_folder / video_path.stem
        video_output_folder.mkdir(exist_ok=True)
        
        successful_segments = 0
        
        # Обрабатываем каждый сегмент
        for i, (start, end) in enumerate(segments, 1):
            duration = end - start
            segment_name = f"{video_path.stem}_part_{i:02d}_({duration:.0f}s).mp4"
            temp_segment_path = video_output_folder / f"temp_{segment_name}"
            final_segment_path = video_output_folder / segment_name
            
            print(f"    📹 Сегмент {i}/{len(segments)}: {start:.1f}s - {end:.1f}s ({duration:.1f}s)")
            
            # Извлекаем сегмент
            if self.extract_segment(video_path, start, end, temp_segment_path):
                print(f"    ✅ Видео сегмент извлечен")
                
                if temp_segment_path.exists():
                    # ВРЕМЕННО ОТКЛЮЧЕНЫ СУБТИТРЫ - только мобильная конвертация
                    print(f"    📱 Создаем мобильную версию...")
                    
                    if self.convert_to_mobile_format(temp_segment_path, final_segment_path):
                        print(f"    ✅ {segment_name} готов (мобильная версия)!")
                        successful_segments += 1
                    else:
                        # Если мобильная версия не создалась, оставляем оригинальную
                        temp_segment_path.rename(final_segment_path)
                        print(f"    ✅ {segment_name} готов (оригинальная версия)")
                        successful_segments += 1
                    
                    # Удаляем временный файл
                    if temp_segment_path.exists():
                        temp_segment_path.unlink()
                else:
                    print(f"    ❌ Временный файл сегмента не найден")
            else:
                print(f"    ❌ Не удалось создать сегмент {i}")
        
        print(f"  🎯 Успешно создано сегментов: {successful_segments}/{len(segments)}")
    
    def run(self):
        """Основной метод запуска обработки"""
        print("🚀 Запуск автоматического процессора видео для шортсов")
        print("=" * 60)
        
        # Проверяем наличие FFmpeg
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, text=True)
            print("✅ FFmpeg найден")
            # Показываем версию для диагностики
            version_line = result.stdout.split('\n')[0] if result.stdout else "версия неизвестна"
            print(f"   📋 {version_line}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ FFmpeg не найден! Установите FFmpeg и добавьте в PATH")
            print("   💡 Для корректной работы субтитров нужна полная версия FFmpeg")
            print("   🔗 Инструкции: https://ffmpeg.org/download.html")
            return
        
        # Проверяем наличие видеофайлов
        video_files = self.find_video_files()
        
        if not video_files:
            print(f"📂 Видеофайлы не найдены в папке: {self.input_folder}")
            print("💡 Поместите видеофайлы в папку 'input_videos' и запустите скрипт снова")
            
            # Создаем примерный файл с инструкцией
            instruction_file = self.input_folder / "ПОМЕСТИТЕ_СЮДА_ВИДЕО.txt"
            with open(instruction_file, 'w', encoding='utf-8') as f:
                f.write("Поместите ваши видеофайлы в эту папку и запустите скрипт заново.\n\n")
                f.write("Поддерживаемые форматы:\n")
                f.write("- MP4, AVI, MKV, MOV\n")
                f.write("- WMV, FLV, WebM, M4V\n\n")
                f.write("После обработки готовые шортсы появятся в папке 'output_shorts'")
            
            return
        
        print(f"📁 Найдено видеофайлов: {len(video_files)}")
        for video in video_files:
            print(f"  📄 {video.name}")
        
        print(f"\n⚙️ Настройки:")
        print(f"   🕐 Минимальная длительность сегмента: {self.min_duration} сек")
        print(f"   🕘 Максимальная длительность сегмента: {self.max_duration} сек")
        print(f"   📝 Субтитры: {'✅ включены (Whisper)' if self.whisper_model else '❌ отключены'}")
        
        # Обрабатываем каждое видео
        total_processed = 0
        for video_path in video_files:
            try:
                self.process_video(video_path)
                total_processed += 1
            except Exception as e:
                print(f"❌ Ошибка при обработке {video_path.name}: {e}")
                continue
        
        print("\n" + "=" * 60)
        print(f"🎉 Обработка завершена!")
        print(f"📊 Обработано видео: {total_processed}/{len(video_files)}")
        print(f"📁 Результаты сохранены в: {self.output_folder}")
        print("\n💡 Готовые шортсы можно найти в папке 'output_shorts'")


def main():
    """Главная функция"""
    processor = VideoShortsProcessor()
    processor.run()


if __name__ == "__main__":
    main()