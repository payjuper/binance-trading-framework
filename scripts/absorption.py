import pandas as pd
import os

# 📁 folder path where the extracted CSV files are located
csv_folder = r"C:\Users\user\Desktop\BN_DATA\BTCUSDT_1m_data\extracted_csv"

df_list = []

# 📄 read all CSV files in the folder
for file in os.listdir(csv_folder):
    if file.endswith(".csv"):
        file_path = os.path.join(csv_folder, file)
        df = pd.read_csv(file_path, header=None)
        df_list.append(df)

# 🔗 merge into a single DataFrame
df_all = pd.concat(df_list, ignore_index=True)

# 🏷️ set column names
df_all.columns = [
    "timestamp", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_vol", "taker_buy_quote_vol", "ignore"
]

# 🧼 convert timestamp to numeric (avoid errors if mixed types)
df_all["timestamp"] = pd.to_numeric(df_all["timestamp"], errors="coerce")

# ⏱️ sort by timestamp and reset index
df_all.sort_values("timestamp", inplace=True)
df_all.reset_index(drop=True, inplace=True)

# 📆 add datetime column
df_all["datetime"] = pd.to_datetime(df_all["timestamp"], unit="ms")

# 💾 save as CSV (include market in filename)
output_path = "btc_usdt_1m_merged.csv"
df_all.to_csv(output_path, index=False)

# ✅ done
print("✅ Merge complete. Total rows:", len(df_all))
print("📄 Saved file:", output_path)
print(df_all.head())
