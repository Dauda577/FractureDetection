"""
model.py -- FracNet architecture definition only.

MAIN MODEL: stop-gradient encoder present (bottleneck.detach() before
the classifier), classification trained with standard CrossEntropyLoss
(Dice 0.6402, IoU 0.5235, AUROC 0.9665). This is the final deployed
checkpoint, chosen over an alternative Focal Loss variant.

No training code here -- this file only defines the network. Load
trained weights via load_fracnet_bundle() in inference.py.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import resnet34, ResNet34_Weights

IMAGE_SIZE = 512


class DoubleConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.conv(x)


class AttentionGate(nn.Module):
    def __init__(self, F_g, F_l, F_int):
        super().__init__()
        self.W_g = nn.Sequential(nn.Conv2d(F_g, F_int, kernel_size=1, bias=True), nn.BatchNorm2d(F_int))
        self.W_x = nn.Sequential(nn.Conv2d(F_l, F_int, kernel_size=1, bias=True), nn.BatchNorm2d(F_int))
        self.psi = nn.Sequential(nn.Conv2d(F_int, 1, kernel_size=1, bias=True), nn.Sigmoid())
        self.relu = nn.ReLU(inplace=True)

    def forward(self, g, skip):
        alpha = self.psi(self.relu(self.W_g(g) + self.W_x(skip)))
        return skip * alpha


class DecoderBlock(nn.Module):
    def __init__(self, in_channels, skip_channels, out_channels, use_attention=True, dropout_p=0.15):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_channels, out_channels, kernel_size=2, stride=2)
        self.use_attention = use_attention
        if use_attention:
            self.att = AttentionGate(F_g=out_channels, F_l=skip_channels, F_int=max(skip_channels // 2, 1))
        self.conv = DoubleConv(out_channels + skip_channels, out_channels)
        self.dropout = nn.Dropout2d(p=dropout_p)  # used by MC-Dropout aleatoric uncertainty

    def forward(self, x, skip):
        x = self.up(x)
        if self.use_attention:
            skip = self.att(x, skip)
        x = torch.cat([x, skip], dim=1)
        x = self.conv(x)
        x = self.dropout(x)
        return x


class FracNet(nn.Module):
    """
    Dual-task Attention U-Net (segmentation + classification).

    Stop-gradient design: the classifier reads the shared encoder's
    bottleneck features via .detach(), so classification loss never
    influences the encoder during training -- segmentation loss alone
    shapes the shared representation. This is the final deployed
    checkpoint (Dice 0.6402), trained with standard CrossEntropyLoss.
    """

    def __init__(self, pretrained_encoder=False):
        super().__init__()
        weights = ResNet34_Weights.IMAGENET1K_V1 if pretrained_encoder else None
        backbone = resnet34(weights=weights)

        self.initial = nn.Sequential(backbone.conv1, backbone.bn1, backbone.relu)
        self.pool = backbone.maxpool
        self.encoder1 = backbone.layer1
        self.encoder2 = backbone.layer2
        self.encoder3 = backbone.layer3
        self.encoder4 = backbone.layer4

        self.gap = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(
            nn.Flatten(), nn.Linear(512, 128), nn.ReLU(), nn.Dropout(0.3), nn.Linear(128, 2)
        )

        self.decoder4 = DecoderBlock(512, 256, 256)
        self.decoder3 = DecoderBlock(256, 128, 128)
        self.decoder2 = DecoderBlock(128, 64, 64)
        self.decoder1 = DecoderBlock(64, 64, 32)
        self.segmentation_head = nn.Conv2d(32, 1, kernel_size=1)

        self.last_features = None  # bottleneck, used by Mahalanobis OOD scoring

    def forward(self, x):
        x0 = self.initial(x)
        x1 = self.pool(x0)
        x2 = self.encoder1(x1)
        x3 = self.encoder2(x2)
        x4 = self.encoder3(x3)
        bottleneck = self.encoder4(x4)

        self.last_features = bottleneck
        # Stop-gradient: classifier reads the bottleneck but cannot send
        # gradient back into it -- matches this checkpoint's training config.
        class_logits = self.classifier(self.gap(bottleneck.detach()))

        d4 = self.decoder4(bottleneck, x4)
        d3 = self.decoder3(d4, x3)
        d2 = self.decoder2(d3, x2)
        d1 = self.decoder1(d2, x0)
        mask_logits = self.segmentation_head(d1)
        mask_logits = F.interpolate(mask_logits, size=(IMAGE_SIZE, IMAGE_SIZE), mode="bilinear", align_corners=False)

        return mask_logits, class_logits


def build_model(device):
    """Convenience constructor -- no pretrained ImageNet download needed
    since trained weights get loaded immediately after via load_fracnet_bundle()."""
    model = FracNet(pretrained_encoder=False).to(device)
    return model
