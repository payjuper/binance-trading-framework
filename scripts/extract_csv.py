import zipfile
import os

# 📁 folder containing the ZIP files (placed one level up from scripts/)
zip_folder = r"C:\Users\user\Desktop\binance-vision-data-pipeline\BTCUSDT_1m_data"

# 📂 output folder to store extracted CSV files
csv_output_folder = os.path.join(zip_folder, "extracted_csv")
os.makedirs(csv_output_folder, exist_ok=True)

# 🔄 loop through all ZIP files in the folder
for file_name in os.listdir(zip_folder):
    if file_name.endswith(".zip"):
        zip_path = os.path.join(zip_folder, file_name)
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for zip_info in zip_ref.infolist():
                    if zip_info.filename.endswith(".csv"):
                        target_path = os.path.join(csv_output_folder, os.path.basename(zip_info.filename))
                        with open(target_path, 'wb') as f_out:
                            f_out.write(zip_ref.read(zip_info.filename))
                        print(f"✅ Extracted: {zip_info.filename}")
        except Exception as e:
            print(f"❌ Error in {file_name}: {e}")
