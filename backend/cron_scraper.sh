#!/bin/bash
# ============================================================
# ProcureAI 定时爬虫 + 数据合并脚本
# 使用方式:
#   1. 放到公司内部服务器上
#   2. crontab -e 添加: 0 3 * * * /opt/procureai/cron_scraper.sh
#   3. 每天凌晨 3:00 自动执行
# ============================================================

set -e

# 配置
PROJECT_DIR="/opt/procureai/backend"
SCRAPER_SCRIPT="/opt/procureai/scraper/wlw_scraper.py"
SCRAPED_OUTPUT="$PROJECT_DIR/scraped_suppliers.json"
LOG_FILE="$PROJECT_DIR/logs/cron.log"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"

# 日志
mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date)] Cron started" >> "$LOG_FILE"

# Step 1: 运行爬虫
echo "[$(date)] Running scraper..." >> "$LOG_FILE"
if $VENV_PYTHON "$SCRAPER_SCRIPT" --output "$SCRAPED_OUTPUT" 2>> "$LOG_FILE"; then
    echo "[$(date)] Scraper completed, output: $SCRAPED_OUTPUT" >> "$LOG_FILE"
else
    echo "[$(date)] Scraper FAILED — using cached data" >> "$LOG_FILE"
    # Plan B: 用上次缓存的数据
    if [ ! -f "$SCRAPED_OUTPUT" ]; then
        echo "[$(date)] No cached data, aborting" >> "$LOG_FILE"
        exit 1
    fi
fi

# Step 2: 合并到主数据库（去重、更新、淘汰旧数据）
echo "[$(date)] Merging scraped data..." >> "$LOG_FILE"
$VENV_PYTHON "$PROJECT_DIR/merge_scraped.py" --input "$SCRAPED_OUTPUT" 2>> "$LOG_FILE"

echo "[$(date)] Cron finished" >> "$LOG_FILE"
