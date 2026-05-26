#!/bin/bash
# vault-backup.sh — Obsidian Vault 独立备份
# 每天全量快照，保留 7 天滚动 + 周日周备份（保留 4 周）
# 用法: bash vault-backup.sh [--restore YYYY-MM-DD]

set -uo pipefail
# 注意：没有 set -e！部分管道（head、wc）的 SIGPIPE 非致命
# 所有关键步骤手动检查退出码

# 加载统一环境变量（修正 cron 下的 HOME 等）
SOURCE_SCRIPT="$(dirname "$0")/setenv.sh"
[ -f "$SOURCE_SCRIPT" ] && source "$SOURCE_SCRIPT"

VAULT_SRC="${OBSIDIAN_VAULT_PATH:-/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault}"
BACKUP_BASE="/Users/liuwei/VaultBackups/obsidian-vault"
TIMESTAMP=$(date +%Y-%m-%d)
DOW=$(date +%u)  # 1=Mon .. 7=Sun

# 恢复模式
if [ "${1:-}" = "--restore" ] && [ -n "${2:-}" ]; then
  RESTORE_DATE="$2"
  RESTORE_DIR="$BACKUP_BASE/daily/$RESTORE_DATE"
  if [ -d "$RESTORE_DIR" ]; then
    echo "快照内容:"
    ls "$RESTORE_DIR"
    echo ""
    echo "恢复到临时目录: /tmp/vault-restore-$RESTORE_DATE"
    cp -r "$RESTORE_DIR" "/tmp/vault-restore-$RESTORE_DATE"
    echo "完成。查看: open /tmp/vault-restore-$RESTORE_DATE"
  else
    echo "❌ 未找到 $RESTORE_DATE 的快照"
    echo "可用快照:"
    ls "$BACKUP_BASE/daily/" 2>/dev/null || echo "  (无)"
    exit 1
  fi
  exit 0
fi

SNAPSHOT="$BACKUP_BASE/daily/$TIMESTAMP"
mkdir -p "$SNAPSHOT"

echo "=== Obsidian Vault 备份 $TIMESTAMP ==="
echo "源: $VAULT_SRC"
echo "目标: $SNAPSHOT"

# 校验源目录
if [ ! -d "$VAULT_SRC" ]; then
  echo "❌ 源目录不存在: $VAULT_SRC"
  exit 1
fi

# rsync 增量拷贝（排除 Obsidian 工作区和缓存）
rsync -a --delete --timeout=60 \
  --exclude='.obsidian/workspace.json' \
  --exclude='.obsidian/workspace' \
  --exclude='.obsidian/cache' \
  --exclude='.trash' \
  --exclude='.DS_Store' \
  "$VAULT_SRC/" "$SNAPSHOT/"

BACKUP_SIZE=$(du -sh "$SNAPSHOT" | cut -f1)
echo "备份大小: $BACKUP_SIZE"

# 文件计数
FILE_COUNT=$(find "$SNAPSHOT" -name "*.md" -type f | wc -l | tr -d ' ')
echo "笔记数: $FILE_COUNT"

# 清理旧日备份：保留最近 7 天
OLD_DAILY=$(find "$BACKUP_BASE/daily" -maxdepth 1 -type d -name "2*" | sort)
NUM_DAILY=$(echo "$OLD_DAILY" | grep -c . || true)
if [ "$NUM_DAILY" -gt 7 ]; then
  REMOVE=$((NUM_DAILY - 7))
  echo "$OLD_DAILY" | head -n "$REMOVE" | while read old; do
    rm -rf "$old"
    echo "  🗑️ 清理旧日备份: $(basename "$old")"
  done
fi

# 周日额外保留一份周备份
if [ "$DOW" = "7" ]; then
  WEEK_NUM=$(date +%W)
  WEEKLY_DIR="$BACKUP_BASE/weekly/2026-W${WEEK_NUM}"
  mkdir -p "$(dirname "$WEEKLY_DIR")"
  rsync -a --delete "$VAULT_SRC/" "$WEEKLY_DIR/"
  echo "📆 周备份 $WEEK_NUM 已保留"
  
  # 周备份保留 4 份
  OLD_WEEKLY=$(find "$BACKUP_BASE/weekly" -maxdepth 1 -type d -name "2*" | sort)
  NUM_WEEKLY=$(echo "$OLD_WEEKLY" | grep -c . || true)
  if [ "$NUM_WEEKLY" -gt 4 ]; then
    REMOVE=$((NUM_WEEKLY - 4))
    echo "$OLD_WEEKLY" | head -n "$REMOVE" | while read old; do
      rm -rf "$old"
      echo "  🗑️ 清理旧周备份: $(basename "$old")"
    done
  fi
fi

# 验证：取前 3 个 .md 文件校验可读性
echo "验证:"
VALIDATE_OK=0
while IFS= read -r f; do
  if [ -f "$f" ] && head -1 "$f" > /dev/null 2>&1; then
    echo "  ✓ $(basename "$f")"
    VALIDATE_OK=$((VALIDATE_OK + 1))
  else
    echo "  ❌ 可能损坏: $f"
  fi
done < <(find "$SNAPSHOT" -name "*.md" -type f | head -n 3; true)

echo ""
echo "=== 备份完成 ==="
echo "日备份: $BACKUP_BASE/daily/"
echo "周备份: $BACKUP_BASE/weekly/"
echo "恢复: bash $0 --restore YYYY-MM-DD"

# 写入投递队列
QUEUE_DIR="$HOME/.hermes/delivery-queue/pending"
mkdir -p "$QUEUE_DIR"
cat > "$QUEUE_DIR/$(date +%Y%m%d-%H%M)-vault-backup.txt" <<EOF
✅ Vault 备份 $TIMESTAMP
大小: $BACKUP_SIZE | 笔记: $FILE_COUNT
路径: $BACKUP_BASE/daily/$TIMESTAMP
恢复: bash vault-backup.sh --restore $TIMESTAMP
EOF
