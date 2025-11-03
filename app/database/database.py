"""
Подключение к базе данных
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
import os

from app.models.database_models import Base


class DatabaseConfig:
    """Конфигурация базы данных"""
    
    def __init__(self):
        # Настройки из переменных окружения
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "shorts_maker")
        self.db_user = os.getenv("DB_USER", "shorts_user")
        self.db_password = os.getenv("DB_PASSWORD", "shorts_password")
        
        # Настройки пула соединений для СКОРОСТИ
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    
    @property
    def database_url(self) -> str:
        """Синхронный URL для миграций"""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def async_database_url(self) -> str:
        """Асинхронный URL для работы приложения"""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


# Глобальная конфигурация
db_config = DatabaseConfig()

# Синхронный движок для миграций
sync_engine = create_engine(
    db_config.database_url,
    pool_size=db_config.pool_size,
    max_overflow=db_config.max_overflow,
    pool_timeout=db_config.pool_timeout,
    pool_recycle=db_config.pool_recycle,
    echo=False  # True для отладки SQL запросов
)

# Асинхронный движок для основной работы
async_engine = create_async_engine(
    db_config.async_database_url,
    pool_size=db_config.pool_size,
    max_overflow=db_config.max_overflow,
    pool_timeout=db_config.pool_timeout,
    pool_recycle=db_config.pool_recycle,
    echo=False  # True для отладки SQL запросов
)

# Фабрика асинхронных сессий
AsyncSessionLocal = sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


@asynccontextmanager
async def get_db_session():
    """
    Контекстный менеджер для работы с БД
    Автоматически закрывает сессию и откатывает транзакции при ошибках
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db():
    """
    Dependency для FastAPI
    Используется в роутах для получения сессии БД
    """
    async with get_db_session() as session:
        yield session


async def init_database():
    """
    Инициализация базы данных
    Создает все таблицы если их нет
    """
    async with async_engine.begin() as conn:
        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)
        print("База данных инициализирована")


async def close_database():
    """
    Закрытие соединений с БД при завершении приложения
    """
    await async_engine.dispose()
    print("Соединения с БД закрыты")


# Функции для миграций (синхронные)
def create_tables():
    """Создание таблиц (для миграций)"""
    Base.metadata.create_all(bind=sync_engine)
    print("Таблицы созданы")


def drop_tables():
    """Удаление таблиц (для сброса БД)"""
    Base.metadata.drop_all(bind=sync_engine)
    print("Таблицы удалены")