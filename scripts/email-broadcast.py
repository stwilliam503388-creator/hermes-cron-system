#!/usr/bin/env python3
"""email-broadcast.py — 广播内容到邮箱（凭证从 ~/.hermes/.env 读取）

支持自动生成语音摘要（MP3 附件）。
语音使用 edge-tts（微软神经网络 TTS），支持多种声线选择。

用法:
  <command> | python3 email-broadcast.py <subject>                  # 从 stdin 读取
  python3 email-broadcast.py <subject> --file <path>                # 从文件读取
  python3 email-broadcast.py <subject> -m "内容"                    # 直接传内容
  python3 email-broadcast.py <subject> --voice zh-CN-YunxiNeural   # 指定男声
  python3 email-broadcast.py <subject> --voice-list                # 列出可用声线
  python3 email-broadcast.py <subject> --no-voice                  # 跳过语音生成

声线速查（中文）:
  女声: Xiaoxiao (暖) / Xiaoyi (活泼)
  男声: Yunxi (阳光) / Yunjian (激情) / Yunyang (专业)
  方言: Xiaobei (东北) / Xiaoni (陕西)
  粤语: HiuGaai (女) / WanLung (男)
  台普: HsiaoChen (女) / YunJhe (男)
"""
import sys
import smtplib
import argparse
import subprocess
import os
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.audio import MIMEAudio
from email.utils import formataddr

# ── 从 .env 加载凭证 ──
def _load_env():
    env = {}
    env_path = "/Users/liuwei/.hermes/.env"
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip().replace("export ", "", 1)
                val = val.strip().strip("\"'")
                env[key] = val
    except (FileNotFoundError, IOError):
        pass
    return env

_env = _load_env()

FROM_ADDR = _env.get("SMTP_FROM", "")
PASSWORD = _env.get("SMTP_PASSWORD", "")
TO_ADDRS = [a.strip() for a in _env.get("SMTP_TO", "").split(",") if a.strip()]
SMTP_HOST = _env.get("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(_env.get("SMTP_PORT", "465"))

if not PASSWORD or not TO_ADDRS or not FROM_ADDR:
    print("ERROR: SMTP credentials not found in ~/.hermes/.env (SMTP_FROM, SMTP_PASSWORD, SMTP_TO)", file=sys.stderr)
    sys.exit(1)

# ── 声线速查表 ──
VOICE_HELP = {
    "female": ["zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural"],
    "male": ["zh-CN-YunxiNeural", "zh-CN-YunjianNeural", "zh-CN-YunyangNeural", "zh-CN-YunxiaNeural"],
    "dialect": ["zh-CN-liaoning-XiaobeiNeural", "zh-CN-shaanxi-XiaoniNeural"],
    "cantonese": ["zh-HK-HiuGaaiNeural", "zh-HK-WanLungNeural"],
    "taiwan": ["zh-TW-HsiaoChenNeural", "zh-TW-YunJheNeural"],
}

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

def list_voices():
    """列出所有可用中文声线"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "edge_tts", "--list-voices"],
            capture_output=True, text=True, timeout=30
        )
        for line in result.stdout.splitlines():
            if "zh-" in line:
                print(line)
    except Exception as e:
        print(f"获取声线列表失败: {e}", file=sys.stderr)

def generate_voice(text, voice_name, output_path):
    """生成语音 MP3 文件"""
    if not text or not text.strip():
        return False
    # 截取前 500 字，太长 edge-tts 会超时
    summary = text.strip()[:500]
    try:
        subprocess.run(
            [sys.executable, "-m", "edge_tts",
             "--text", summary,
             "--voice", voice_name,
             "--write-media", output_path],
            capture_output=True, timeout=120, check=True
        )
        return os.path.getsize(output_path) > 0
    except subprocess.CalledProcessError as e:
        print(f"语音生成失败: {e.stderr.decode() if e.stderr else e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"语音生成异常: {e}", file=sys.stderr)
        return False

parser = argparse.ArgumentParser(description="发送邮件，支持语音附件")
parser.add_argument("subject", nargs="?", default="Cron Job")
parser.add_argument("--file", help="从文件读取内容")
parser.add_argument("-m", "--message", help="直接传内容")
parser.add_argument("--voice", default=DEFAULT_VOICE, help="声线名称（默认 XiaoxiaoNeural 女声）")
parser.add_argument("--voice-list", action="store_true", help="列出可用中文声线")
parser.add_argument("--no-voice", action="store_true", help="跳过语音生成")
args = parser.parse_args()

if args.voice_list:
    list_voices()
    sys.exit(0)

body = None
if args.message:
    body = args.message
elif args.file:
    with open(args.file) as f:
        body = f.read()
else:
    body = sys.stdin.read()

if not body or not body.strip():
    sys.exit(0)

# ── 构建邮件（支持语音附件）──
msg = MIMEMultipart("mixed")
msg["From"] = formataddr(("AI Agent Broadcast", FROM_ADDR))
msg["To"] = ", ".join(TO_ADDRS)
msg["Subject"] = args.subject

# 正文部分
text_part = MIMEText(body, "plain", "utf-8")
msg.attach(text_part)

# 语音附件部分
if not args.no_voice:
    voice_name = args.voice
    # 验证声线是否包含 "zh-"，防止拼写错误
    if "zh-" not in voice_name and "Neural" not in voice_name:
        print(f"警告: 声线名 {voice_name} 看起来不像有效中文声线，使用默认 {DEFAULT_VOICE}", file=sys.stderr)
        voice_name = DEFAULT_VOICE

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        mp3_path = tmp.name

    print(f"正在生成语音（声线: {voice_name}）...", file=sys.stderr)
    ok = generate_voice(body, voice_name, mp3_path)

    if ok and os.path.exists(mp3_path):
        file_size = os.path.getsize(mp3_path)
        if file_size > 100:  # 至少 100 字节才算有效
            with open(mp3_path, "rb") as f:
                audio_part = MIMEAudio(f.read(), _subtype="mp3")
                audio_part.add_header("Content-Disposition", "attachment", filename="voice-summary.mp3")
                msg.attach(audio_part)
            print(f"语音附件已添加: {file_size / 1024:.1f} KB", file=sys.stderr)
        else:
            print(f"语音文件过小 ({file_size} bytes)，跳过附件", file=sys.stderr)
        try:
            os.unlink(mp3_path)
        except OSError:
            pass
    else:
        print("语音生成失败，邮件继续发送（无语音附件）", file=sys.stderr)

# ── 发送 ──
with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as srv:
    srv.login(FROM_ADDR, PASSWORD)
    srv.sendmail(FROM_ADDR, TO_ADDRS, msg.as_string())
