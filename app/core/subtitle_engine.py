"""
Движок субтитров
СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
"""
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional

try:
    import whisper
except ImportError:
    whisper = None


class SubtitleEngine:
    """Класс для работы с субтитрами"""
    
    def __init__(self, whisper_model_name: str = "base"):
        """
        Инициализация движка субтитров
        
        Args:
            whisper_model_name: Название модели Whisper для загрузки
        """
        self.whisper_model_name = whisper_model_name
        self.whisper_model = None
        
        # ВРЕМЕННО ОТКЛЮЧЕНО как в оригинальном скрипте
        print("Модель Whisper отключена для быстрого тестирования...")
        # try:
        #     if whisper is not None:
        #         self.whisper_model = whisper.load_model(whisper_model_name)
        #         print("Модель Whisper загружена")
        # except Exception as e:
        #     print(f"Ошибка загрузки Whisper: {e}")
        #     print("Субтитры будут отключены")
        #     self.whisper_model = None
    
    def generate_subtitles(self, video_path: Path) -> str:
        """
        Генерирует субтитры для видео используя Whisper
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        
        Args:
            video_path: Путь к видеофайлу
            
        Returns:
            str: SRT контент или пустая строка если ошибка
        """
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
            print(f"    Ошибка при генерации субтитров: {e}")
            return ""
    
    def seconds_to_srt_time(self, seconds: float) -> str:
        """
        Конвертирует секунды в формат времени SRT
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def srt_time_to_seconds(self, time_str: str) -> float:
        """
        Конвертирует время SRT (00:00:01,500) в секунды
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        """
        try:
            # Формат: HH:MM:SS,mmm
            time_part, ms_part = time_str.split(',')
            hours, minutes, seconds = map(int, time_part.split(':'))
            milliseconds = int(ms_part)
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
            return total_seconds
        except Exception:
            return 0.0
    
    def parse_srt_content(self, srt_content: str) -> List[Dict]:
        """
        Парсит SRT контент в список словарей с временными метками
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        """
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
                    print(f"     Ошибка парсинга блока: {e}")
                    continue
        
        return entries
    
    def add_subtitles_with_drawtext(self, video_path: Path, srt_content: str, output_path: Path) -> bool:
        """
        Альтернативный способ - используем drawtext для каждой строки субтитров
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        """
        try:
            # Парсим SRT контент
            subtitle_entries = self.parse_srt_content(srt_content)
            
            if not subtitle_entries:
                print("     Не удалось распарсить субтитры для drawtext")
                return False
            
            print(f"     Используем drawtext для {len(subtitle_entries)} фрагментов субтитров")
            
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
            
            print(f"     Способ 2: Используем drawtext...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"     Субтитры встроены через drawtext!")
                return True
            else:
                print(f"     Drawtext тоже не сработал")
                return False
                
        except Exception as e:
            print(f"     Ошибка в drawtext методе: {e}")
            return False
    
    def add_subtitles_to_video(self, video_path: Path, srt_content: str, output_path: Path) -> bool:
        """
        Добавляет субтитры к видео - РАБОЧАЯ ВЕРСИЯ С ПРЯМЫМ ПУТЕМ К ШРИФТУ
        
        СКОПИРОВАНО ИЗ ОРИГИНАЛЬНОГО СКРИПТА БЕЗ ИЗМЕНЕНИЙ
        
        Args:
            video_path: Путь к исходному видео
            srt_content: Содержимое SRT файла
            output_path: Путь для сохранения результата
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        if not srt_content.strip():
            print("     Пустые субтитры, сохраняем видео без них")
            shutil.copy2(video_path, output_path)
            return True
        
        # Сохраняем субтитры во временный файл
        srt_path = output_path.parent / f"temp_{output_path.stem}.srt"
        
        try:
            # Записываем SRT файл
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            print(f"     Временный SRT файл создан: {srt_path.name}")
            
            # Проверяем что файл создался
            if not srt_path.exists():
                print(f"     Не удалось создать файл субтитров")
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
            
            print(f"    Способ 1: Встраиваем субтитры с прямым путем к шрифту...")
            print(f"    Команда: ffmpeg -i {video_path.name} [subtitles+font] {output_path.name}")
            
            result1 = subprocess.run(cmd1, capture_output=True, text=True)
            
            if result1.returncode == 0:
                print(f"    Субтитры успешно встроены!")
                return True
            else:
                print(f"    Способ 1 не сработал, пробуем drawtext...")
                
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
                
                print(f"    Способ 3: Простые субтитры без шрифта...")
                result3 = subprocess.run(cmd3, capture_output=True, text=True)
                
                if result3.returncode == 0:
                    print(f"    Субтитры встроены (простой вариант)")
                    return True
                else:
                    print(f"    Все способы не сработали, сохраняем без субтитров")
                    shutil.copy2(video_path, output_path)
                    return True
                
        except Exception as e:
            print(f"    Общая ошибка при обработке субтитров: {e}")
            try:
                shutil.copy2(video_path, output_path)
                print(f"    Видео сохранено без субтитров")
                return True
            except Exception as copy_error:
                print(f"    Ошибка при копировании видео: {copy_error}")
                return False
        finally:
            # Убираем временный SRT файл
            if srt_path.exists():
                try:
                    srt_path.unlink()
                except:
                    pass