#!/bin/bash
# Hermes 配置文件备份脚本
# 每次运行生成带时间戳的快照，保留最近 30 个

# 自动检测 Hermes 真实 HOME（应对 cron 环境下的 $HOME 重映射）
if echo "$HOME" | grep -q "\.hermes/profiles/"; then
  HERMES_HOME="/Users/liuwei"
else
  HERMES_HOME="${HERMES_HOME:-$HOME}"
fi
BACKUP_DIR="$HERMES_HOME/.hermes/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SNAPSHOT="$BACKUP_DIR/$TIMESTAMP"
MAX_KEEP=30

mkdir -p "$SNAPSHOT"

echo "=== Config Backup $TIMESTAMP ==="

copied=0

# 核心文件（必须存在）
copy_file() {
  local label="$1" src="$2"
  if [ -f "$src" ]; then
    local dest="$SNAPSHOT/$label"
    mkdir -p "$(dirname "$dest")"
    cp "$src" "$dest"
    echo "  ✅ $label"
    copied=$((copied + 1))
  else
    echo "  ⚠️  $label (missing)"
  fi
}

copy_file "hermes/config.yaml" "$HERMES_HOME/.hermes/config.yaml"
copy_file "hermes/cron/jobs.json" "$HERMES_HOME/.hermes/cron/jobs.json"

# 可选目录（存在才备份）
if [ -d "$HERMES_HOME/.hermes/skills" ]; then
    cp -r "$HERMES_HOME/.hermes/skills" "$SNAPSHOT/skills/"
    echo "  ✅ skills (dir)"
    copied=$((copied + 1))
fi

# 元信息
cat > "$SNAPSHOT/backup_info.yaml" <<EOF
backup_time: $(date -Iseconds)
hostname: $(hostname)
user: $(whoami)
hermes_version: $(hermes --version 2>/dev/null || echo unknown)
files_copied: $copied
EOF

# 旋转：只保留最近 MAX_KEEP 个
ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null | awk "NR>$MAX_KEEP" | while read -r old; do
  rm -rf "$old"
  echo "  🗑️  pruned: $(basename "$old")"
done

echo "=== Done: $TIMESTAMP ($copied files) ==="
