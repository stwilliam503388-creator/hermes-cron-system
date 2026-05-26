#!/bin/bash
# hermes-backup.sh — backup critical Hermes config data to compressed archive
# Only backs up irreplaceable data: config, skills, cron jobs, plugins, memory, SOUL.md
# Excludes: source code, sessions, logs, cache, sandbox venv (all reproducible)
#
# Usage: hermes-backup.sh [backup|restore|list] [args...]
set -euo pipefail

REAL_HOME=$(eval echo ~$USER)
HERMES_HOME="${REAL_HOME}/.hermes"
BACKUP_DIR="${BACKUP_DIR:-$REAL_HOME/backups/hermes}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT="${BACKUP_DIR}/hermes-backup-${TIMESTAMP}.tar.zst"

# Critical paths — irreplaceable, small, high-value
CRITICAL_PATHS=(
    "config.yaml"
    ".env"
    "SOUL.md"
    "auth.json"
    "profiles/minimal/config.yaml"
    "profiles/minimal/.env"
    "profiles/minimal/SOUL.md"
    "profiles/minimal/skills"
    "profiles/minimal/cron"
    "profiles/minimal/plugins"
)

log()  { echo "[hermes-backup] $*" >&2; }
die()  { log "ERROR: $*"; exit 1; }

cmd_backup() {
    local dry=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) dry=true; shift ;;
            -o) OUTPUT="$2"; shift 2 ;;
            *) die "Unknown flag: $1" ;;
        esac
    done

    mkdir -p "$BACKUP_DIR"

    if $dry; then
        log "DRY RUN — would backup:"
        for p in "${CRITICAL_PATHS[@]}"; do
            local full="$HERMES_HOME/$p"
            [[ -e "$full" ]] && echo "  $p" || echo "  $p (MISSING)"
        done
        log "Output: $OUTPUT"
        return 0
    fi

    # Build include list from existing paths
    local include=()
    for p in "${CRITICAL_PATHS[@]}"; do
        local full="$HERMES_HOME/$p"
        [[ -e "$full" ]] && include+=("$p")
    done

    log "Backing up ${#include[@]} paths to: $OUTPUT"
    tar -cf - -C "$HERMES_HOME" "${include[@]}" | zstd -T0 -o "$OUTPUT"

    local size=$(du -h "$OUTPUT" | cut -f1)
    log "Done: $OUTPUT ($size)"
    echo "$OUTPUT"
}

cmd_restore() {
    local archive="" force=false dry=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force) force=true; shift ;;
            --dry-run) dry=true; shift ;;
            -*) die "Unknown flag: $1" ;;
            *) archive="$1"; shift ;;
        esac
    done
    [[ -z "$archive" ]] && die "Usage: restore <archive.tar.zst>"
    [[ ! -f "$archive" ]] && die "Not found: $archive"

    if $dry; then
        log "DRY RUN — would restore to $HERMES_HOME:"
        zstd -d -c "$archive" | tar -tvf - | head -30
        return 0
    fi

    if ! $force; then
        log "Use --force to overwrite existing files."
        exit 1
    fi

    log "Restoring from: $archive"
    zstd -d -c "$archive" | tar -xf - -C "$HERMES_HOME"
    log "Done."
}

cmd_list() {
    ls -lh "$BACKUP_DIR"/*.tar.zst 2>/dev/null || log "(no backups yet)"
}

ACTION="${1:-backup}"
shift || true
case "$ACTION" in
    backup)  cmd_backup "$@" ;;
    restore) cmd_restore "$@" ;;
    list)    cmd_list "$@" ;;
    *)       die "Use: backup | restore | list" ;;
esac
