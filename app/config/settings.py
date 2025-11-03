"""
Настройки приложения с поддержкой БД
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
    max_file_size: int = 1000000000  # 1GB
    
    # База данных
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "shorts_maker"
    db_user: str = "shorts_user"
    db_password: str = "shorts_password_2024"
    
    # Настройки пула соединений
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    
    # Режим работы БД
    use_database: bool = True  # False для работы без БД (JSON файлы)
    
    # Настройки обработки по умолчанию
    min_duration_default: int = 60
    max_duration_default: int = 180
    enable_subtitles_default: bool = False
    mobile_scale_default: float = 1.2
    
    # Whisper настройки
    whisper_model: str = "base"
    
    # Настройки для анализа
    scene_detection_threshold: float = 0.3
    silence_threshold_db: float = -30.0
    silence_duration_seconds: float = 1.0
    
    @property
    def allowed_extensions(self) -> List[str]:
        """Возвращает список поддерживаемых расширений"""
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
        """Возвращает set поддерживаемых расширений"""
        return {ext.lower() for ext in self.allowed_extensions}
    
    @property
    def database_url(self) -> str:
        """Синхронный URL для миграций"""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def async_database_url(self) -> str:
        """Асинхронный URL для работы приложения"""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


# Глобальный экземпляр настроек
settings = Settings()