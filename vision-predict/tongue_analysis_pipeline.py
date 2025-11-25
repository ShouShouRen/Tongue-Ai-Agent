# tongue_analysis_pipeline.py - 完整的舌診分析流程
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch
import torchvision.transforms as T
from model import UNetWithSwinEncoder, SimpleTimmModel
import sys
import json

def segment_tongue(image_path, segmentation_model_path="swim_trasnformer_384.pth"):
    """步驟1: 使用 UNet 分割舌頭"""
    print("步驟 1/4: 分割舌頭...")
    
    THRESHOLD = 0.5
    backbone = 'swin_base_patch4_window12_384'
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 預處理
    transform = T.Compose([
        T.Resize((384, 384)),
        T.ToTensor(),
        T.Normalize([0.5]*3, [0.5]*3),
    ])
    
    # 載入分割模型
    model = UNetWithSwinEncoder(backbone_name=backbone).to(device)
    model.load_state_dict(torch.load(segmentation_model_path, map_location=device, weights_only=False))
    model.eval()
    
    # 讀取圖片
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    
    # 預測 mask
    input_tensor = transform(image).unsqueeze(0).to(device)
    with torch.no_grad():
        output = model(input_tensor)
        output = torch.sigmoid(output)
        pred = (output > THRESHOLD).float()
    
    # resize mask 回原圖大小
    pred_mask = pred.squeeze().cpu().numpy()
    mask_resized = np.array(
        Image.fromarray((pred_mask * 255).astype("uint8")).resize((width, height), Image.NEAREST)
    ) / 255.0
    
    # 套用 mask
    mask_exp = np.expand_dims(mask_resized, axis=-1)
    img_np = np.array(image)
    segmented_np = (img_np * mask_exp).astype(np.uint8)
    
    print("  ✓ 舌頭分割完成")
    return segmented_np, mask_resized, np.array(image)

def extract_tongue_roi(segmented_image, mask):
    """步驟2: 提取舌頭 ROI (去除黑色背景，只保留舌頭區域)"""
    print("步驟 2/4: 提取舌頭 ROI...")
    
    # 找到舌頭的邊界框
    rows = np.any(mask > 0.5, axis=1)
    cols = np.any(mask > 0.5, axis=0)
    
    if not rows.any() or not cols.any():
        print("  ⚠ 警告: 未檢測到舌頭區域")
        return None, None
    
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    
    # 裁剪出舌頭區域
    tongue_roi = segmented_image[rmin:rmax+1, cmin:cmax+1]
    
    print(f"  ✓ ROI 提取完成: {tongue_roi.shape[1]}x{tongue_roi.shape[0]} -> 384x384")
    return Image.fromarray(tongue_roi), (rmin, rmax, cmin, cmax)

def predict_tongue_condition(tongue_roi_image, classification_model_path="Simple_convnext_base_fold3.pth", output_format="structured"):
    """步驟3: 使用分類模型預測舌象特徵"""
    print("步驟 3/4: 分析舌象特徵...")
    
    # 標籤定義
    labels = ['TonguePale', 'TipSideRed', 'Spot', 'Ecchymosis',
              'Crack', 'Toothmark', 'FurThick', 'FurYellow']
    chinese_labels = ['舌淡白', '舌尖邊紅', '紅點', '瘀斑', '裂紋', '齒痕', '苔厚', '苔黃']
    best_threshold = [0.4, 0.55, 0.85, 0.55, 0.1, 0.35, 0.15, 0.65]
    
    # 載入分類模型
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SimpleTimmModel(
        num_classes=8, 
        backbone='convnext_base',
        feature_dim=512,
        img_size=384
    )
    
    checkpoint = torch.load(classification_model_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()
    
    # 圖像預處理 (調整為 384x384)
    transform = T.Compose([
        T.Resize((384, 384)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    image_tensor = transform(tongue_roi_image).unsqueeze(0).to(device)
    
    # 預測
    with torch.no_grad():
        outputs = model(image_tensor, image_tensor, image_tensor, image_tensor, image_tensor)
        probs = torch.sigmoid(outputs).cpu().numpy()[0]
    
    # 整理結果
    positive_results = []
    negative_results = []
    
    for eng, chi, prob, thresh in zip(labels, chinese_labels, probs, best_threshold):
        result = {
            'chinese': chi,
            'english': eng,
            'probability': float(prob),
            'threshold': float(thresh)
        }
        
        if prob > thresh:
            positive_results.append(result)
        else:
            negative_results.append(result)
    
    print(f"  ✓ 特徵分析完成: 檢測到 {len(positive_results)} 個陽性症狀")
    
    return {
        'positive': positive_results,
        'negative': negative_results,
        'summary': {
            'positive_count': len(positive_results),
            'negative_count': len(negative_results)
        }
    }

def create_visualization(original_image, segmented_image, roi_image, bbox, output_path="analysis_result.jpg"):
    """創建視覺化對比圖"""
    # 轉換為 PIL Image
    original_pil = Image.fromarray(original_image)
    segmented_pil = Image.fromarray(segmented_image)
    
    # 在原圖上標註 bbox
    original_with_bbox = original_pil.copy()
    draw = ImageDraw.Draw(original_with_bbox)
    if bbox is not None:
        rmin, rmax, cmin, cmax = bbox
        draw.rectangle([cmin, rmin, cmax, rmax], outline="red", width=3)
    
    # 調整 ROI 大小以便顯示
    if roi_image is not None:
        roi_display = roi_image.resize((384, 384), Image.LANCZOS)
    else:
        roi_display = Image.new('RGB', (384, 384), color='black')
    
    # 調整其他圖像大小
    h, w = original_image.shape[:2]
    aspect_ratio = w / h
    if aspect_ratio > 1:
        new_w, new_h = 400, int(400 / aspect_ratio)
    else:
        new_h, new_w = 400, int(400 * aspect_ratio)
    
    original_display = original_with_bbox.resize((new_w, new_h), Image.LANCZOS)
    segmented_display = segmented_pil.resize((new_w, new_h), Image.LANCZOS)
    
    # 創建畫布
    canvas_width = new_w * 2 + 384 + 40
    canvas_height = max(new_h, 384) + 100
    canvas = Image.new('RGB', (canvas_width, canvas_height), color='white')
    
    # 貼上圖像
    y_offset = 60
    canvas.paste(original_display, (10, y_offset))
    canvas.paste(segmented_display, (new_w + 20, y_offset))
    canvas.paste(roi_display, (new_w * 2 + 30, y_offset))
    
    # 添加標題
    draw = ImageDraw.Draw(canvas)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font_title = ImageFont.load_default()
        font_label = ImageFont.load_default()
    
    # 繪製標題
    draw.text((canvas_width // 2 - 100, 10), "Tongue Analysis Pipeline", fill="black", font=font_title)
    
    # 繪製標籤
    draw.text((10, y_offset - 30), "1. Original (with ROI)", fill="black", font=font_label)
    draw.text((new_w + 20, y_offset - 30), "2. Segmented", fill="black", font=font_label)
    draw.text((new_w * 2 + 30, y_offset - 30), "3. ROI (384x384)", fill="black", font=font_label)
    
    # 保存
    canvas.save(output_path, quality=95)
    return output_path

def display_results(results, output_format="structured"):
    """步驟4: 顯示結果"""
    print("\n步驟 4/4: 輸出分析結果")
    print("=" * 60)
    
    if output_format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("\n【檢測到的症狀】")
        if results['positive']:
            for r in results['positive']:
                print(f"  • {r['chinese']}({r['english']}): {r['probability']:.3f}")
        else:
            print("  無")
        
        print("\n【未檢測到的症狀】")
        if results['negative']:
            for r in results['negative']:
                print(f"  • {r['chinese']}({r['english']}): {r['probability']:.3f}")
        else:
            print("  無")
        
        print(f"\n【統計】")
        print(f"  陽性症狀: {results['summary']['positive_count']} 個")
        print(f"  陰性症狀: {results['summary']['negative_count']} 個")

def analyze_tongue_image(
    image_path, 
    segmentation_model_path="swim_trasnformer_384.pth",
    classification_model_path="Simple_convnext_base_fold3.pth",
    output_format="structured",
    output_dir="output"
):
    """完整的舌診分析流程"""
    
    print("=" * 60)
    print("舌診影像分析系統")
    print("=" * 60)
    print(f"輸入圖片: {image_path}\n")
    
    # 創建輸出目錄
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成輸出文件名
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    
    try:
        # 步驟 1: 分割舌頭
        segmented_image, mask, original_image = segment_tongue(image_path, segmentation_model_path)
        
        # 保存分割結果
        segmented_path = os.path.join(output_dir, f"{base_name}_segmented.jpg")
        Image.fromarray(segmented_image).save(segmented_path)
        
        # 步驟 2: 提取 ROI
        tongue_roi, bbox = extract_tongue_roi(segmented_image, mask)
        
        if tongue_roi is None:
            print("\n❌ 錯誤: 無法提取舌頭區域")
            return None
        
        # 保存 ROI
        roi_path = os.path.join(output_dir, f"{base_name}_roi.jpg")
        tongue_roi.save(roi_path)
        
        # 創建視覺化對比圖
        visualization_path = os.path.join(output_dir, f"{base_name}_analysis.jpg")
        create_visualization(original_image, segmented_image, tongue_roi, bbox, visualization_path)
        
        # 步驟 3: 預測舌象特徵
        results = predict_tongue_condition(tongue_roi, classification_model_path, output_format)
        
        # 步驟 4: 顯示結果
        display_results(results, output_format)
        
        # 保存 JSON 結果
        json_path = os.path.join(output_dir, f"{base_name}_result.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 顯示保存的文件
        print("\n【輸出文件】")
        print(f"  • 分割結果: {segmented_path}")
        print(f"  • ROI 圖像: {roi_path}")
        print(f"  • 分析對比: {visualization_path}")
        print(f"  • JSON 結果: {json_path}")
        
        print("\n" + "=" * 60)
        print("✅ 分析完成！請檢查輸出圖像確認分割品質。")
        print("=" * 60)
        
        return results
        
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python tongue_analysis_pipeline.py <圖像路徑> [輸出格式] [輸出目錄]")
        print("\n範例:")
        print("  python tongue_analysis_pipeline.py selfie.jpg")
        print("  python tongue_analysis_pipeline.py selfie.jpg json")
        print("  python tongue_analysis_pipeline.py selfie.jpg structured results")
        print("\n參數說明:")
        print("  輸出格式: structured (預設) 或 json")
        print("  輸出目錄: 預設為 'output'")
    else:
        image_path = sys.argv[1]
        output_format = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] in ["json", "structured"] else "structured"
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "output"
        
        analyze_tongue_image(
            image_path,
            output_format=output_format,
            output_dir=output_dir
        )
