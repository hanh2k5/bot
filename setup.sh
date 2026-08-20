#!/usr/bin/env bash
echo "========================================================"
echo "  LEADHUNTER BOT - TỰ ĐỘNG CÀI ĐẶT 1 CLICK CHO MÁY MỚI"
echo "========================================================"
echo ""
echo "1. Đang cài đặt các thư viện Python..."
python3 -m pip install -e . --break-system-packages 2>/dev/null || python3 -m pip install -e . || pip3 install -e .
echo ""
echo "2. Đang tải trình duyệt Playwright Chromium (cần kết nối mạng)..."
python3 -m playwright install chromium
echo ""
echo "========================================================"
echo "  HOÀN TẤT! Từ bây giờ bạn chỉ cần gõ lệnh: run"
echo "========================================================"
