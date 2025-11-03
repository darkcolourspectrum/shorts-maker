"""
Дополнительные роуты для Telegram бота
"""
import zipfile
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.video_service import video_service
from app.config.settings import settings

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram_bot"])


@router.get("/download-zip/{task_id}")
async def download_task_as_zip(task_id: str):
    """
    Создает и отдает ZIP архив со всеми результатами задачи
    Специально для Telegram бота
    """
    # Получаем статус задачи
    task_status = video_service.get_task_status(task_id)
    
    if not task_status:
        raise HTTPException(
            status_code=404,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    if task_status['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Задача еще не завершена. Статус: {task_status['status']}"
        )
    
    result_files = task_status.get('result_files', [])
    if not result_files:
        raise HTTPException(
            status_code=404,
            detail="Нет готовых файлов для скачивания"
        )
    
    # Создаем временный ZIP файл
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
        temp_zip_path = Path(temp_zip.name)
    
    try:
        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_url in result_files:
                # Преобразуем URL в путь к файлу
                # /api/v1/download/task_123/video_part_01.mp4 -> task_123/video_part_01.mp4
                file_path_str = file_url.replace('/api/v1/download/', '')
                full_file_path = settings.output_path_obj / file_path_str
                
                if full_file_path.exists():
                    # Добавляем файл в архив с красивым именем
                    arcname = full_file_path.name
                    zipf.write(full_file_path, arcname)
        
        # Имя для скачивания
        original_filename = task_status.get('filename', 'video')
        zip_filename = f"{Path(original_filename).stem}_shorts.zip"
        
        return FileResponse(
            path=str(temp_zip_path),
            filename=zip_filename,
            media_type='application/zip',
            background=lambda: temp_zip_path.unlink(missing_ok=True)  # Удаляем после отправки
        )
        
    except Exception as e:
        # Очищаем временный файл при ошибке
        temp_zip_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании архива: {str(e)}"
        )


@router.get("/task-info/{task_id}")
async def get_task_info_for_bot(task_id: str):
    """
    Получает информацию о задаче в формате удобном для бота
    """
    task_status = video_service.get_task_status(task_id)
    
    if not task_status:
        raise HTTPException(
            status_code=404,
            detail=f"Задача с ID {task_id} не найдена"
        )
    
    # Добавляем ссылку на ZIP если задача завершена
    if task_status['status'] == 'completed' and task_status.get('result_files'):
        task_status['zip_download_url'] = f"/api/v1/telegram/download-zip/{task_id}"
    
    return task_status