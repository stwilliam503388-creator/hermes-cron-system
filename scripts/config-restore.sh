#!/bin/bash
# 快速恢复配置文件备份
# 用法: bash ~/.hermes/scripts/config-restore.sh [snapshot_dir]
#       不传参数则恢复最新的备份

BACKUP_DIR="$HOME/.hermes/backups"

if [ -n "${1:-}" ]; then
  SNAPSHOT="$1"
else
  SNAPSHOT=$(ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null | head -1)
fi

if [ -z "$SNAPSHOT" ] || [ ! -d "$SNAPSHOT" ]; then
  echo "❌ No backup found at: ${SNAPSHOT:-$BACKUP_DIR}"
  echo ""
  echo "Available backups:"
  ls -1dt "$BACKUP_DIR"/*/ 2>/dev/null | while read d; do
    echo "  $(basename "$d")"
  done
  exit 1
fi

echo "=== Restore from: $(basename "$SNAPSHOT") ==="

# 恢复映射: snapshot相对路径 → 系统绝对路径
declare -A RESTORE_MAP=(
  ["hermes/config.yaml"]="$HOME/.hermes/config.yaml"
  ["hermes/.env"]="$HOME/.hermes/.env"
  ["shell/.zshrc"]="$HOME/.zshrc"
)

for snap_path in "${!RESTORE_MAP[@]}"; do
  src="$SNAPSHOT/$snap_path"
  dest="${RESTORE_MAP[$snap_path]}"
  if [ -f "$src" ]; then
    cp "$src" "$dest"
    echo "  ✅ restored: $dest"
  else
    echo "  ⚠️  missing in snapshot: $snap_path"
  fi
done

echo "=== Restore complete ==="
echo ""
echo "Skills backup at: $SNAPSHOT/skills/ (manual restore if needed)"
