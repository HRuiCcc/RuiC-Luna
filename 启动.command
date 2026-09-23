#!/bin/bash
# 双击本文件：启动本地服务器并打开月球页面（真实数据模式需要 HTTP，不能直接 file:// 打开）
cd "$(dirname "$0")" || exit 1
PORT=8899
while lsof -i :$PORT >/dev/null 2>&1; do PORT=$((PORT+1)); done
echo "月球 LUNA · 观测器"
echo "  本地地址： http://127.0.0.1:$PORT/index.html"
echo "  真实数据： $(ls -sh data/moon_h.bin 2>/dev/null | awk '{print $1}') 高程 + $(ls -sh data/moon_a.bin 2>/dev/null | awk '{print $1}') 反照率（LRO LOLA + LROC WAC）"
echo "  按 Control-C 或关闭本窗口即可停止服务器。"
( sleep 1.2; open "http://127.0.0.1:$PORT/index.html" ) &
python3 -m http.server $PORT --bind 127.0.0.1
