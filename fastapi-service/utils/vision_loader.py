# utils/vision_loader.py
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path
import sys
import logging

logger = logging.getLogger(__name__)

@dataclass
class VisionPredictStatus:
    is_available: bool
    error_message: Optional[str] = None
    analyze_function: Optional[Callable] = None
    
class VisionPredictLoader:
    def __init__(self, base_path: Path, verbose: bool = True):
        self.base_path = base_path.resolve()
        self.verbose = verbose
        self.status = self._load()
    
    def _load(self) -> VisionPredictStatus:
        """載入 vision-predict 模組"""
        if self.verbose:
            print(f"嘗試載入 vision-predict 模組...")
            print(f"vision-predict 路徑: {self.base_path}")
            print(f"路徑存在: {self.base_path.exists()}")
        
        try:
            # 檢查路徑
            if not self.base_path.exists():
                error_msg = f"Path does not exist: {self.base_path}"
                if self.verbose:
                    print(f"✗ {error_msg}")
                return VisionPredictStatus(
                    is_available=False,
                    error_message=error_msg
                )
            
            # 添加到 sys.path
            if str(self.base_path) not in sys.path:
                sys.path.insert(0, str(self.base_path))
                if self.verbose:
                    print(f"已添加路徑到 sys.path: {self.base_path}")
            
            # 檢查依賴
            self._check_dependencies()
            if self.verbose:
                print("✓ 所有必要的依賴項已安裝")
            
            # 導入模組
            from tongue_analysis_pipeline import analyze_tongue_image
            if self.verbose:
                print("✓ 成功導入 tongue_analysis_pipeline")
            
            # 檢查模型文件
            segmentation_model = self.base_path / "swim_trasnformer_384.pth"
            classification_model = self.base_path / "Simple_convnext_base_fold3.pth"
            
            if not segmentation_model.exists():
                if self.verbose:
                    print(f"⚠ 警告: 分割模型文件不存在: {segmentation_model}")
            else:
                if self.verbose:
                    print(f"✓ 分割模型文件存在: {segmentation_model}")
            
            if not classification_model.exists():
                if self.verbose:
                    print(f"⚠ 警告: 分類模型文件不存在: {classification_model}")
            else:
                if self.verbose:
                    print(f"✓ 分類模型文件存在: {classification_model}")
            
            # 建立包裝函數
            analyze_fn = self._create_wrapper(analyze_tongue_image)
            
            if self.verbose:
                print("✓ vision-predict 模組已成功載入並配置")
            
            return VisionPredictStatus(
                is_available=True,
                analyze_function=analyze_fn
            )
            
        except ImportError as e:
            error_msg = f"缺少必要的依賴項: {e}"
            if self.verbose:
                print(f"✗ {error_msg}")
                import traceback
                traceback.print_exc()
            return VisionPredictStatus(
                is_available=False,
                error_message=error_msg
            )
        except Exception as e:
            error_msg = f"載入 vision-predict 時發生錯誤: {str(e)}"
            if self.verbose:
                print(f"✗ {error_msg}")
                import traceback
                traceback.print_exc()
            return VisionPredictStatus(
                is_available=False,
                error_message=error_msg
            )
    
    def _check_dependencies(self):
        """檢查必要依賴"""
        required = ['torch', 'torchvision', 'timm', 'PIL', 'numpy']
        missing = []
        
        for package in required:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        if missing:
            raise ImportError(f"缺少必要的依賴項: {', '.join(missing)}")
    
    def _create_wrapper(self, analyze_fn):
        """建立包裝函數"""
        segmentation_model = self.base_path / "swim_trasnformer_384.pth"
        classification_model = self.base_path / "Simple_convnext_base_fold3.pth"
        
        def wrapper(image_path, output_format="structured", output_dir=None):
            import tempfile
            if output_dir is None:
                output_dir = tempfile.mkdtemp()
            
            return analyze_fn(
                image_path=image_path,
                segmentation_model_path=str(segmentation_model),
                classification_model_path=str(classification_model),
                output_format=output_format,
                output_dir=output_dir
            )
        
        return wrapper
