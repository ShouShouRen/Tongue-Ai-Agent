# utils/vision_loader.py
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path
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
        """載入 vision_predict 模組"""
        if self.verbose:
            print(f"嘗試載入 vision_predict 模組...")
            print(f"模型路徑: {self.base_path}")
            print(f"路徑存在: {self.base_path.exists()}")

        try:
            # 檢查路徑
            if not self.base_path.exists():
                error_msg = f"Path does not exist: {self.base_path}"
                if self.verbose:
                    print(f"✗ {error_msg}")
                return VisionPredictStatus(is_available=False, error_message=error_msg)

            # 檢查依賴
            self._check_dependencies()
            if self.verbose:
                print("✓ 所有必要的依賴項已安裝")

            # 直接 import（不需要 sys.path hack）
            from vision_predict.tongue_analysis_pipeline import analyze_tongue_image
            if self.verbose:
                print("✓ 成功導入 vision_predict.tongue_analysis_pipeline")

            # 檢查模型文件
            segmentation_model = self.base_path / "ukan_model.pth"
            classification_model = self.base_path / "Simple_convnext_base_fold3.pth"

            for label, path in [("分割模型", segmentation_model), ("分類模型", classification_model)]:
                if self.verbose:
                    if path.exists():
                        print(f"✓ {label}文件存在: {path}")
                    else:
                        print(f"⚠ 警告: {label}文件不存在: {path}")

            # 建立包裝函數
            analyze_fn = self._create_wrapper(analyze_tongue_image)

            if self.verbose:
                print("✓ vision_predict 模組已成功載入並配置")

            return VisionPredictStatus(is_available=True, analyze_function=analyze_fn)

        except ImportError as e:
            error_msg = f"缺少必要的依賴項: {e}"
            if self.verbose:
                print(f"✗ {error_msg}")
                import traceback
                traceback.print_exc()
            return VisionPredictStatus(is_available=False, error_message=error_msg)
        except Exception as e:
            error_msg = f"載入 vision_predict 時發生錯誤: {str(e)}"
            if self.verbose:
                print(f"✗ {error_msg}")
                import traceback
                traceback.print_exc()
            return VisionPredictStatus(is_available=False, error_message=error_msg)

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
        segmentation_model = self.base_path / "ukan_model.pth"
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
