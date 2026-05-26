#!/bin/bash
# setenv.sh — 统一环境变量配置
# 被所有 Obsidian 相关脚本 source 加载
# 单点真相源：所有脚本统一通过此文件获取 vault 路径

export OBSIDIAN_VAULT_PATH="/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
export HERMES_SCRIPTS="/Users/liuwei/.hermes/scripts"

export NOTEBOOKLM_VENV="/Users/liuwei/.hermes/notebooklm_venv/bin/python"
export VAULT_BACKUP_DIR="/Users/liuwei/VaultBackups/obsidian-vault"

# 修正 HOME（cron 环境 $HOME 指向 profile 目录，导致 Path.home() 等出错）
export HOME="/Users/liuwei"
