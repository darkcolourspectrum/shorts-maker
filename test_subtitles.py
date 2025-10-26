#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы встраивания субтитров
"""

import subprocess
import tempfile
from pathlib import Path

def test_subtitle_embedding():
    """Тестирует встраивание субтитров"""
    print("🧪 Тестируем встраивание субтитров...")
    
    # Проверяем FFmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, text=True)
        print("✅ FFmpeg найден")
        version_line = result.stdout.split('\n')[0] if result.stdout else "версия неизвестна"
        print(f"   📋 {version_line}")
        
        # Проверяем тип сборки
        if 'essentials' in result.stdout.lower():
            print("   ⚠️ Обнаружена 'essentials' сборка - может быть проблема с субтитрами")
        elif 'full' in result.stdout.lower():
            print("   ✅ Полная сборка FFmpeg")
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg не найден!")
        return False
    
    # Создаем тестовый SRT файл
    test_srt_content = """1
00:00:00,000 --> 00:00:05,000
Это тестовые субтитры

2
00:00:05,000 --> 00:00:10,000
Проверяем встраивание в видео

3
00:00:10,000 --> 00:00:15,000
Hello World!
"""
    
    # Проверяем есть ли видеофайлы в input_videos
    input_folder = Path("input_videos")
    if not input_folder.exists():
        print(f"❌ Папка {input_folder} не найдена")
        return False
    
    video_files = list(input_folder.glob("*.mp4"))
    if not video_files:
        print(f"❌ MP4 файлы не найдены в {input_folder}")
        print("💡 Поместите тестовое видео в папку input_videos")
        return False
    
    test_video = video_files[0]
    print(f"📹 Используем тестовое видео: {test_video.name}")
    
    # Создаем временные файлы
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as srt_file:
        srt_file.write(test_srt_content)
        srt_path = Path(srt_file.name)
    
    success = False
    
    # ТЕСТ 1: Проверяем subtitles фильтр с прямым путем к шрифту
    print("\n🔧 ТЕСТ 1: subtitles фильтр с прямым путем к шрифту")
    output_path1 = Path("test_subtitles_method1.mp4")
    
    srt_path_str = str(srt_path.absolute()).replace('\\', '/')
    cmd1 = [
        'ffmpeg',
        '-i', str(test_video.absolute()),
        '-vf', f"subtitles={srt_path_str}:fontfile=C\\:/Windows/Fonts/arial.ttf:fontsize=24:fontcolor=white:outline=1:outlinecolor=black",
        '-c:a', 'copy',
        '-t', '20',  # Только первые 20 секунд для теста
        '-y',
        str(output_path1.absolute())
    ]
    
    try:
        result1 = subprocess.run(cmd1, capture_output=True, text=True)
        if result1.returncode == 0:
            print("✅ ТЕСТ 1 ПРОЙДЕН: subtitles с прямым путем к шрифту работает!")
            success = True
        else:
            print("❌ ТЕСТ 1 НЕ ПРОЙДЕН")
            print("📋 Последние строки ошибки:")
            if result1.stderr:
                error_lines = result1.stderr.strip().split('\n')[-3:]
                for line in error_lines:
                    if line.strip():
                        print(f"   ⚠️ {line}")
    except Exception as e:
        print(f"❌ ТЕСТ 1 - исключение: {e}")
    
    # ТЕСТ 2: Проверяем drawtext
    print("\n🔧 ТЕСТ 2: drawtext метод")
    output_path2 = Path("test_drawtext_method2.mp4")
    
    cmd2 = [
        'ffmpeg',
        '-i', str(test_video.absolute()),
        '-vf', "drawtext=fontfile=C\\\\:/Windows/Fonts/arial.ttf:text='Test Subtitle':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=h-th-20:enable='between(t,2,8)'",
        '-c:a', 'copy',
        '-t', '15',  # Только первые 15 секунд для теста
        '-y',
        str(output_path2.absolute())
    ]
    
    try:
        result2 = subprocess.run(cmd2, capture_output=True, text=True)
        if result2.returncode == 0:
            print("✅ ТЕСТ 2 ПРОЙДЕН: drawtext метод работает!")
            success = True
        else:
            print("❌ ТЕСТ 2 НЕ ПРОЙДЕН")
            print("📋 Последние строки ошибки:")
            if result2.stderr:
                error_lines = result2.stderr.strip().split('\n')[-3:]
                for line in error_lines:
                    if line.strip():
                        print(f"   ⚠️ {line}")
    except Exception as e:
        print(f"❌ ТЕСТ 2 - исключение: {e}")
    
    # ТЕСТ 3: Простые субтитры без шрифта
    print("\n🔧 ТЕСТ 3: простые субтитры без указания шрифта")
    output_path3 = Path("test_simple_subtitles.mp4")
    
    cmd3 = [
        'ffmpeg',
        '-i', str(test_video.absolute()),
        '-vf', f"subtitles={srt_path_str}",
        '-c:a', 'copy',
        '-t', '20',  # Только первые 20 секунд для теста
        '-y',
        str(output_path3.absolute())
    ]
    
    try:
        result3 = subprocess.run(cmd3, capture_output=True, text=True)
        if result3.returncode == 0:
            print("✅ ТЕСТ 3 ПРОЙДЕН: простые субтитры работают!")
            success = True
        else:
            print("❌ ТЕСТ 3 НЕ ПРОЙДЕН")
            print("📋 Последние строки ошибки:")
            if result3.stderr:
                error_lines = result3.stderr.strip().split('\n')[-3:]
                for line in error_lines:
                    if line.strip():
                        print(f"   ⚠️ {line}")
    except Exception as e:
        print(f"❌ ТЕСТ 3 - исключение: {e}")
    
    # Показываем результаты
    print(f"\n📊 РЕЗУЛЬТАТЫ ТЕСТОВ:")
    for i, output_path in enumerate([output_path1, output_path2, output_path3], 1):
        if output_path.exists():
            file_size = output_path.stat().st_size / (1024*1024)
            print(f"   ✅ Тест {i}: {output_path.name} ({file_size:.1f} МБ)")
        else:
            print(f"   ❌ Тест {i}: файл не создан")
    
    # Убираем временный SRT файл
    if srt_path.exists():
        srt_path.unlink()
    
    return success

if __name__ == "__main__":
    success = test_subtitle_embedding()
    if success:
        print("\n🎉 Хотя бы один метод работает! Субтитры можно встраивать.")
        print("💡 Проверьте созданные тестовые файлы чтобы увидеть результат.")
    else:
        print("\n❌ Ни один метод не сработал. Проверьте:")
        print("   - Установлена ли полная версия FFmpeg")
        print("   - Есть ли файл C:/Windows/Fonts/arial.ttf") 
        print("   - Доступны ли права на запись в текущую папку")