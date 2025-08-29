import requests
from datetime import datetime
import os

# ✅ config: start year/month and end year/month
start_year = 2024
start_month = 1
end_year = 2025
end_month = 8   # up to August 2025

# ✅ save folder
save_dir = "BTCUSDT_1m_data"
os.makedirs(save_dir, exist_ok=True)

# ✅ Binance USDT-M URL (BTCUSDT, 1m interval)
base_url = "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1m/"

# ✅ download loop
current = datetime(start_year, start_month, 1)
end = datetime(end_year, end_month, 1)

while current <= end:
    date_str = current.strftime("%Y-%m")
    file_name = f"BTCUSDT-1m-{date_str}.zip"
    file_path = os.path.join(save_dir, file_name)
    url = base_url + file_name

    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(res.content)
            print(f"✅ Downloaded: {file_name}")
        else:
            print(f"❌ Not found: {file_name}")
    except Exception as e:
        print(f"⚠️ Error downloading {file_name}: {e}")

    # move to next month
    if current.month == 12:
        current = current.replace(year=current.year + 1, month=1)
    else:
        current = current.replace(month=current.month + 1)
