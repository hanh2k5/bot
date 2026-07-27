import sys
from leadhunter.infrastructure.adapters.google_maps_scraper import GoogleMapsScraper
scraper = GoogleMapsScraper(None, None)
names = [
    "Cứu Hộ Xe Máy Quận Tân Bình Sửa Xe Tại Nhà",
    "Sửa Xe Máy 171 Cộng Hoà",
    "SỬA XE THANH TUẤN | SỬA XE TAY GA TÂN BÌNH",
    "Cửa hàng Sửa chữa Xe máy Duy Thịnh",
    "Cửa Hàng Sửa Chữa Xe Máy Hùng"
]

# We must use the exact function inside scrape_fast
# Wait, _is_place_id_or_junk is a nested function!
# We can just copy it exactly from the file!
