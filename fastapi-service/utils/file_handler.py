# utils/file_handler.py
from contextlib import contextmanager
import tempfile
import shutil
from pathlib import Path
from typing import Optional

class TempFileManager:
    """臨時檔案管理器"""
    
    @staticmethod
    @contextmanager
    def temp_image(upload_file, suffix: Optional[str] = None):
        """管理上傳的臨時圖片"""
        if suffix is None:
            suffix = Path(upload_file.filename).suffix
        
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            shutil.copyfileobj(upload_file.file, tmp_file)
            tmp_file.close()
            yield tmp_file.name
        finally:
            Path(tmp_file.name).unlink(missing_ok=True)
    
    @staticmethod
    @contextmanager
    def temp_dir():
        """管理臨時目錄"""
        tmp_dir = tempfile.mkdtemp()
        try:
            yield tmp_dir
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

# 使用方式
async def predict_tongue_image(file: UploadFile = File(...)):
    with TempFileManager.temp_image(file) as image_path:
        with TempFileManager.temp_dir() as output_dir:
            results = analyze_tongue_image(
                image_path=image_path,
                output_dir=output_dir
            )
            return results
