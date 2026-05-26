#!/bin/bash
# =============================================================
# setup-automation-deps.sh — 安装剩余自动化任务的依赖
# 运行: bash ~/.hermes/scripts/setup-automation-deps.sh
# =============================================================
echo "═══ Hermes 自动化依赖安装 ═══"
echo ""

# ── 1. faster-whisper（播客转文字）──
echo "▶ 安装 faster-whisper..."
if pip3 show faster-whisper &>/dev/null; then
    echo "  ✓ 已安装"
else
    pip3 install faster-whisper 2>&1 | tail -3
    echo "  ✓ faster-whisper 安装完成"
fi
echo ""

# ── 2. ComfyUI 检查 ──
echo "▶ 检查 ComfyUI..."
if [ -d ~/ComfyUI ]; then
    echo "  ✓ ComfyUI 已存在"
else
    echo "  ⚠️ ComfyUI 未安装（可选，用于AI绘画任务）"
    echo "  安装方式: git clone https://github.com/comfyanonymous/ComfyUI.git ~/ComfyUI"
    echo "  然后: cd ~/ComfyUI && pip install -r requirements.txt"
fi
echo ""

# ── 3. 验证脚本可执行 ──
echo "▶ 验证脚本..."
for script in system-alert.sh browser-tabs-archive.sh sleep-weekly-report.sh price-monitor.sh; do
    if [ -f ~/.hermes/scripts/$script ]; then
        chmod +x ~/.hermes/scripts/$script
        echo "  ✓ $script"
    else
        echo "  ✗ $script 不存在"
    fi
done
echo ""

echo "═══ 完成 ═══"
echo "运行 hermes cron list 查看所有定时任务"
