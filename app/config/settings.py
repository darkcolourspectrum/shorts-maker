"""
Настройки приложения
Перенесено из оригинального скрипта main.py
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List


class Settings(BaseSettings):
    """Настройки приложения"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra='ignore'
    )
    
    # API настройки
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # Пути к папкам
    upload_path: str = "./storage/input"
    output_path: str = "./storage/output"
    temp_path: str = "./storage/temp"
    
    # Настройки файлов
    max_file_size: int = 500000000  # 500MB
    
    # Настройки обработки по умолчанию (из оригинального скрипта)
    min_duration_default: int = 60
    max_duration_default: int = 180
    enable_subtitles_default: bool = False
    mobile_scale_default: float = 1.2
    
    # Whisper настройки
    whisper_model: str = "base"
    
    # Настройки для анализа (из оригинального скрипта)
    scene_detection_threshold: float = 0.3
    silence_threshold_db: float = -30.0
    silence_duration_seconds: float = 1.0
    
    @property
    def allowed_extensions(self) -> List[str]:
        """Возвращает список поддерживаемых расширений (как в оригинальном скрипте)"""
        return [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"]
    
    @property
    def upload_path_obj(self) -> Path:
        """Возвращает Path объект для папки загрузки"""
        path = Path(self.upload_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def output_path_obj(self) -> Path:
        """Возвращает Path объект для папки результатов"""
        path = Path(self.output_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def temp_path_obj(self) -> Path:
        """Возвращает Path объект для временной папки"""
        path = Path(self.temp_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def video_extensions(self) -> set:
        """Возвращает set поддерживаемых расширений (как в оригинальном скрипте)"""
        return {ext.lower() for ext in self.allowed_extensions}


# Глобальный экземпляр настроек
settings = Settings()