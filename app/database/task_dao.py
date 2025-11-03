"""
DAO для работы с задачами в базе данных
Оптимизировано для СКОРОСТИ
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from datetime import datetime
import time

from app.models.database_models import ProcessingTask, TaskStatus


class TaskDAO:
    """Data Access Object для задач обработки"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_task(self, 
                         task_id: str,
                         filename: str,
                         file_path: str,
                         algorithm: str = "multi_shorts",
                         **kwargs) -> ProcessingTask:
        """
        Создает новую задачу в БД
        БЫСТРО: одиночный INSERT
        """
        task = ProcessingTask(
            task_id=task_id,
            original_filename=filename,
            file_path=file_path,
            algorithm=algorithm,
            status=TaskStatus.QUEUED,
            **kwargs
        )
        
        self.session.add(task)
        await self.session.flush()  # Получаем ID без коммита
        await self.session.refresh(task)
        
        return task
    
    async def get_task_by_id(self, task_id: str) -> Optional[ProcessingTask]:
        """
        Получает задачу по ID
        БЫСТРО: индекс на task_id
        """
        query = select(ProcessingTask).where(ProcessingTask.task_id == task_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update_task_status(self,
                                task_id: str,
                                status: Optional[TaskStatus] = None,
                                progress: Optional[int] = None,
                                message: Optional[str] = None,
                                error_message: Optional[str] = None,
                                result_files: Optional[List[str]] = None,
                                segments_created: Optional[int] = None,
                                processing_time: Optional[float] = None) -> bool:
        """
        Обновляет статус задачи
        БЫСТРО: UPDATE по индексу + только измененные поля
        """
        update_data = {'updated_at': datetime.utcnow()}
        
        if status is not None:
            update_data['status'] = status
            if status == TaskStatus.PROCESSING:
                update_data['started_at'] = datetime.utcnow()
            elif status in [TaskStatus.COMPLETED, TaskStatus.ERROR]:
                update_data['completed_at'] = datetime.utcnow()
        
        if progress is not None:
            update_data['progress'] = progress
        if message is not None:
            update_data['message'] = message
        if error_message is not None:
            update_data['error_message'] = error_message
        if result_files is not None:
            update_data['result_files'] = result_files
        if segments_created is not None:
            update_data['segments_created'] = segments_created
        if processing_time is not None:
            update_data['processing_time'] = processing_time
        
        query = update(ProcessingTask).where(
            ProcessingTask.task_id == task_id
        ).values(**update_data)
        
        result = await self.session.execute(query)
        return result.rowcount > 0
    
    async def get_active_tasks(self, limit: int = 50) -> List[ProcessingTask]:
        """
        Получает активные задачи (queued, processing)
        БЫСТРО: составной индекс idx_status_created
        """
        query = select(ProcessingTask).where(
            ProcessingTask.status.in_([TaskStatus.QUEUED, TaskStatus.PROCESSING])
        ).order_by(desc(ProcessingTask.created_at)).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_tasks_by_status(self, 
                                 status: TaskStatus, 
                                 limit: int = 100) -> List[ProcessingTask]:
        """
        Получает задачи по статусу
        БЫСТРО: индекс на status
        """
        query = select(ProcessingTask).where(
            ProcessingTask.status == status
        ).order_by(desc(ProcessingTask.created_at)).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def delete_old_tasks(self, days: int = 30) -> int:
        """
        Удаляет старые задачи
        Для очистки БД от накопившихся записей
        """
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Сначала получаем задачи для удаления файлов
        query = select(ProcessingTask).where(
            and_(
                ProcessingTask.created_at < cutoff_date,
                ProcessingTask.status.in_([TaskStatus.COMPLETED, TaskStatus.ERROR])
            )
        )
        
        result = await self.session.execute(query)
        old_tasks = result.scalars().all()
        
        # Удаляем файлы (если нужно)
        deleted_count = 0
        for task in old_tasks:
            try:
                # Здесь можно добавить удаление файлов с диска
                # Path(task.file_path).unlink(missing_ok=True)
                await self.session.delete(task)
                deleted_count += 1
            except Exception as e:
                print(f"Ошибка при удалении задачи {task.task_id}: {e}")
        
        return deleted_count
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Получает статистику по задачам
        Для мониторинга и аналитики
        """
        from sqlalchemy import func, case
        
        query = select(
            func.count(ProcessingTask.id).label('total'),
            func.count(case((ProcessingTask.status == TaskStatus.COMPLETED, 1))).label('completed'),
            func.count(case((ProcessingTask.status == TaskStatus.ERROR, 1))).label('failed'),
            func.count(case((ProcessingTask.status == TaskStatus.PROCESSING, 1))).label('processing'),
            func.count(case((ProcessingTask.status == TaskStatus.QUEUED, 1))).label('queued'),
            func.avg(ProcessingTask.processing_time).label('avg_time'),
            func.sum(ProcessingTask.segments_created).label('total_segments')
        )
        
        result = await self.session.execute(query)
        row = result.first()
        
        return {
            'total_tasks': row.total or 0,
            'completed_tasks': row.completed or 0,
            'failed_tasks': row.failed or 0,
            'processing_tasks': row.processing or 0,
            'queued_tasks': row.queued or 0,
            'avg_processing_time': float(row.avg_time or 0),
            'total_segments_created': row.total_segments or 0
        }


# Вспомогательные функции для быстрого доступа
async def create_task_quick(session: AsyncSession, 
                           task_id: str, 
                           filename: str, 
                           file_path: str,
                           **kwargs) -> ProcessingTask:
    """Быстрое создание задачи"""
    dao = TaskDAO(session)
    return await dao.create_task(task_id, filename, file_path, **kwargs)


async def update_task_quick(session: AsyncSession, 
                           task_id: str, 
                           **kwargs) -> bool:
    """Быстрое обновление задачи"""
    dao = TaskDAO(session)
    return await dao.update_task_status(task_id, **kwargs)


async def get_task_quick(session: AsyncSession, 
                        task_id: str) -> Optional[ProcessingTask]:
    """Быстрое получение задачи"""
    dao = TaskDAO(session)
    return await dao.get_task_by_id(task_id)