1. **自動保存三個圖像**：

   - `原始名稱_segmented.jpg`: 分割後的舌頭（背景為黑色）
   - `原始名稱_roi.jpg`: 提取的 ROI（只有舌頭）
   - `原始名稱_analysis.jpg`: 對比圖（原圖+分割+ROI 三合一）

2. **視覺化對比圖**：

   - 左邊：原圖 + 紅色邊界框標註 ROI 位置
   - 中間：分割後的結果
   - 右邊：最終送入分類模型的 ROI

3. **結果展示**：

```
【輸出文件】
  • 分割結果: output/selfie_segmented.jpg
  • ROI 圖像: output/selfie_roi.jpg
  • 分析對比: output/selfie_analysis.jpg

# 基本執行
python tongue_analysis_pipeline.py 指定照片.jpg

# 如果想要 JSON 格式輸出（給 LLM 用）
python tongue_analysis_pipeline.py 指定照片.jpg json

# 如果想指定輸出資料夾
python tongue_analysis_pipeline.py 指定照片.jpg structured my_results

```
