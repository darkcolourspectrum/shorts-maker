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
        print("🤖 Загружаем модель Whisper для субтитров...")
        try:
            self.whisper_model = whisper.load_model("base")
            print("✅ Модель Whisper загружена")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки Whisper: {e}")
            print("📝 Субтитры будут отключены")
            self.whisper_model = None
        
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
    
    def add_subtitles_to_video(self, video_path: Path, srt_content: str, output_path: Path):
        """Добавляет субтитры к видео"""
        # Сохраняем субтитры во временный файл
        srt_path = output_path.parent / f"temp_{output_path.stem}.srt"
        
        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            # Проверяем что файл субтитров создался
            if not srt_path.exists():
                print(f"    ❌ Не удалось создать файл субтитров")
                return False
            
            # Способ 1: Вшиваем субтитры прямо в видео (burned-in)
            video_str = str(video_path)
            output_str = str(output_path)
            
            # Используем простой фильтр subtitles без кавычек
            srt_for_filter = str(srt_path).replace('\\', '/').replace(':', '\\:')
            
            cmd1 = [
                'ffmpeg',
                '-i', video_str,
                '-vf', f'subtitles={srt_for_filter}:force_style=FontName=Arial,FontSize=24,PrimaryColour=&Hffffff',
                '-c:a', 'copy',
                output_str,
                '-y'
            ]
            
            try:
                result = subprocess.run(cmd1, check=True, capture_output=True, text=True)
                print(f"    ✅ Субтитры вшиты в видео")
                return True
            except subprocess.CalledProcessError as e:
                print(f"    ⚠️ Способ 1 не сработал, пробуем упрощенный вариант...")
                
                # Способ 2: Упрощенная команда без стилей
                cmd2 = [
                    'ffmpeg',
                    '-i', video_str,
                    '-vf', f'subtitles={srt_for_filter}',
                    '-c:a', 'copy',
                    output_str,
                    '-y'
                ]
                
                try:
                    subprocess.run(cmd2, check=True, capture_output=True)
                    print(f"    ✅ Субтитры вшиты (упрощенный вариант)")
                    return True
                except subprocess.CalledProcessError as e2:
                    print(f"    ⚠️ Способ 2 тоже не сработал, пробуем через ass файл...")
                    
                    # Способ 3: Конвертируем в ASS и используем его
                    ass_path = srt_path.with_suffix('.ass')
                    self.convert_srt_to_ass(srt_path, ass_path)
                    
                    if ass_path.exists():
                        ass_for_filter = str(ass_path).replace('\\', '/').replace(':', '\\:')
                        cmd3 = [
                            'ffmpeg',
                            '-i', video_str,
                            '-vf', f'ass={ass_for_filter}',
                            '-c:a', 'copy',
                            output_str,
                            '-y'
                        ]
                        
                        try:
                            subprocess.run(cmd3, check=True, capture_output=True)
                            print(f"    ✅ Субтитры вшиты через ASS")
                            ass_path.unlink()  # Удаляем временный ASS
                            return True
                        except subprocess.CalledProcessError as e3:
                            print(f"    ❌ Все способы вшивания не сработали")
                            if ass_path.exists():
                                ass_path.unlink()
                    
                    # Последний способ: просто копируем видео и оставляем .srt рядом
                    print(f"    📄 Сохраняем видео с отдельным .srt файлом")
                    import shutil
                    shutil.copy2(video_path, output_path)
                    
                    # Переименовываем .srt файл чтобы совпадал с видео
                    final_srt_path = output_path.with_suffix('.srt')
                    if final_srt_path.exists():
                        final_srt_path.unlink()
                    srt_path.rename(final_srt_path)
                    
                    print(f"    📝 Субтитры в отдельном файле: {final_srt_path.name}")
                    return True
            
        except Exception as e:
            print(f"    ❌ Ошибка при добавлении субтитров: {e}")
            # В случае ошибки, копируем видео без субтитров
            try:
                import shutil
                shutil.copy2(video_path, output_path)
                print(f"    📄 Видео сохранено без субтитров")
                return True
            except Exception as copy_error:
                print(f"    ❌ Ошибка при копировании видео: {copy_error}")
                return False
        finally:
            # Убираем временные файлы
            for temp_file in [srt_path]:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except:
                        pass
    
    def convert_srt_to_ass(self, srt_path: Path, ass_path: Path):
        """Конвертирует SRT в ASS формат для лучшей совместимости"""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            # Простая конвертация SRT в ASS
            ass_content = """[Script Info]
Title: Auto-generated
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,24,&Hffffff,&Hffffff,&H0,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,30,30,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            
            # Парсим SRT и конвертируем в ASS
            blocks = srt_content.strip().split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    time_line = lines[1]
                    text_lines = lines[2:]
                    
                    # Парсим время
                    if ' --> ' in time_line:
                        start, end = time_line.split(' --> ')
                        start_ass = self.srt_time_to_ass(start)
                        end_ass = self.srt_time_to_ass(end)
                        text = '\\N'.join(text_lines)
                        
                        ass_content += f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}\n"
            
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
                
        except Exception as e:
            print(f"    ⚠️ Ошибка конвертации в ASS: {e}")
    
    def srt_time_to_ass(self, srt_time: str) -> str:
        """Конвертирует время из SRT формата в ASS"""
        # SRT: 00:01:23,456 -> ASS: 0:01:23.46
        srt_time = srt_time.strip()
        if ',' in srt_time:
            time_part, ms_part = srt_time.split(',')
            ms_part = ms_part[:2]  # Берем только первые 2 цифры миллисекунд
            return f"{time_part}.{ms_part}"
        return srt_time
    
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
                print(f"    ✅ Видео сегмент создан")
                
                if temp_segment_path.exists():
                    # Генерируем субтитры
                    if self.whisper_model:
                        print(f"    🤖 Генерируем субтитры...")
                        subtitles = self.generate_subtitles(temp_segment_path)
                        
                        if subtitles:
                            print(f"    📝 Добавляем субтитры...")
                            if self.add_subtitles_to_video(temp_segment_path, subtitles, final_segment_path):
                                successful_segments += 1
                            # Удаляем временный файл
                            if temp_segment_path.exists():
                                temp_segment_path.unlink()
                        else:
                            # Сохраняем без субтитров
                            temp_segment_path.rename(final_segment_path)
                            print(f"    ✅ {segment_name} готов без субтитров")
                            successful_segments += 1
                    else:
                        # Сохраняем без субтитров
                        temp_segment_path.rename(final_segment_path)
                        print(f"    ✅ {segment_name} готов")
                        successful_segments += 1
            else:
                print(f"    ❌ Не удалось создать сегмент {i}")
        
        print(f"  🎯 Успешно создано сегментов: {successful_segments}/{len(segments)}")
    
    def run(self):
        """Основной метод запуска обработки"""
        print("🚀 Запуск автоматического процессора видео для шортсов")
        print("=" * 60)
        
        # Проверяем наличие FFmpeg
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            print("✅ FFmpeg найден")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ FFmpeg не найден! Установите FFmpeg и добавьте в PATH")
            print("   Инструкции: https://ffmpeg.org/download.html")
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
        print(f"   📝 Субтитры: {'включены' if self.whisper_model else 'отключены'}")
        
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