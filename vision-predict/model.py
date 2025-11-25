# model.py - 完整的模型庫
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import torch.nn as nn
import torch.nn.functional as F
import timm
from timm import create_model

# ==================== 分割模型相關 ====================

class DoubleConv(nn.Module):
    """Two consecutive conv-bn-relu blocks"""
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.conv(x)


class UNetWithSwinEncoder(nn.Module):
    """Swin Transformer 作為 Encoder 的 UNet"""
    def __init__(self, backbone_name='swin_base_patch4_window12_384', out_channels=1):
        super().__init__()
        self.encoder = timm.create_model(backbone_name, features_only=True, pretrained=True)
        enc_channels = self.encoder.feature_info.channels()  # [128, 256, 512, 1024]

        # Decoder 結構
        self.up4 = nn.ConvTranspose2d(enc_channels[-1], enc_channels[-1] // 2, kernel_size=2, stride=2)
        self.decoder4 = DoubleConv(enc_channels[-1] // 2 + enc_channels[-2], enc_channels[-2])

        self.up3 = nn.ConvTranspose2d(enc_channels[-2], enc_channels[-2] // 2, kernel_size=2, stride=2)
        self.decoder3 = DoubleConv(enc_channels[-2] // 2 + enc_channels[-3], enc_channels[-3])

        self.up2 = nn.ConvTranspose2d(enc_channels[-3], enc_channels[-3] // 2, kernel_size=2, stride=2)
        self.decoder2 = DoubleConv(enc_channels[-3] // 2 + enc_channels[-4], enc_channels[-4])

        self.up1 = nn.ConvTranspose2d(enc_channels[-4], enc_channels[-4] // 2, kernel_size=2, stride=2)
        self.decoder1 = DoubleConv(enc_channels[-4] // 2, 64)

        self.final = nn.Conv2d(64, out_channels, kernel_size=1)

    def forward(self, x):
        x_input_h, x_input_w = x.shape[2:]
        encs = self.encoder(x)

        # 若特徵圖通道不在 dim=1，就轉成 (B, C, H, W)
        encs = [e.permute(0, 3, 1, 2).contiguous() if e.ndim == 4 and e.shape[1] < e.shape[-1] else e for e in encs]

        x = self.up4(encs[-1])
        if x.shape[2:] != encs[-2].shape[2:]:
            x = F.interpolate(x, size=encs[-2].shape[2:])
        x = torch.cat([x, encs[-2]], dim=1)
        x = self.decoder4(x)

        x = self.up3(x)
        if x.shape[2:] != encs[-3].shape[2:]:
            x = F.interpolate(x, size=encs[-3].shape[2:])
        x = torch.cat([x, encs[-3]], dim=1)
        x = self.decoder3(x)

        x = self.up2(x)
        if x.shape[2:] != encs[-4].shape[2:]:
            x = F.interpolate(x, size=encs[-4].shape[2:])
        x = torch.cat([x, encs[-4]], dim=1)
        x = self.decoder2(x)

        x = self.up1(x)
        x = self.decoder1(x)

        x = self.final(x)
        x = F.interpolate(x, size=(x_input_h, x_input_w), mode='bilinear', align_corners=False)
        return x

# ==================== 分類模型相關 ====================

class SimpleTimmModel(nn.Module):
    """用於多標籤舌象分類的 Timm 模型"""
    def __init__(self, num_classes, backbone='convnext_base', feature_dim=512, img_size=224):
        super().__init__()
        print(f"Initializing SimpleTimmModel with backbone: {backbone}")
        
        # 建立 kwargs 字典
        model_kwargs = {
            'pretrained': True,
            'num_classes': num_classes
        }

        # 智慧判斷：只有 ViT/Swin/DINO 類型的模型才需要 img_size
        if 'vit' in backbone or 'swin' in backbone or 'dinov2' in backbone:
            print(f"  -> (ViT/Swin/DINO) 傳遞 img_size={img_size}")
            model_kwargs['img_size'] = img_size
        else:
            print(f"  -> (CNN) 不傳遞 img_size")

        # 使用 **kwargs 語法來建立模型
        self.model = create_model(backbone, **model_kwargs)

    def forward(self, x_whole, x_root, x_center, x_side, x_tip):
        """
        支援多區域輸入的介面，但目前只使用全圖
        x_whole: 全舌圖像
        x_root, x_center, x_side, x_tip: 舌頭各區域（保留介面）
        """
        return self.model(x_whole)
