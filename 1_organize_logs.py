import os
import shutil
import glob
import sys

# --- 設定 ---
SOURCE_ROOT = "." 
DEST_ROOT = "analyzed_data"

def parse_filename(filename):
    """
    ファイル名からメタデータを抽出する
    対応形式: log_{ParticipantID}_{DateTime}_{Type}_raw.csv
    """
    basename = os.path.basename(filename)
    name_body = basename.replace(".csv", "")
    parts = name_body.split('_')
    
    # log, PID, Date, Type, raw の最低5要素を期待
    if len(parts) >= 5 and parts[-1] == "raw":
        # 形式: log_PID_DateTime_Type_raw
        type_str = parts[-2] # gesture or typing
        pid = parts[1]       # ParticipantID
        
        if type_str not in ["gesture", "typing"]:
            return None

        meta = {
            "ParticipantID": pid,
            "Type": type_str,
            "OriginalName": basename
        }
        return meta
        
    return None

def main():
    print(f"Scanning for log files in '{SOURCE_ROOT}'...")
    
    # 再帰的にファイルを検索
    files = glob.glob(os.path.join(SOURCE_ROOT, "**", "*_raw.csv"), recursive=True)
    
    count = 0
    for file_path in files:
        # 整理済みフォルダ自身はスキップ
        if os.path.abspath(file_path).startswith(os.path.abspath(DEST_ROOT)):
            continue

        meta = parse_filename(file_path)
        
        if meta:
            target_dir = os.path.join(DEST_ROOT, meta["Type"], meta["ParticipantID"])
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
                
            target_path = os.path.join(target_dir, meta["OriginalName"])
            
            try:
                shutil.copy2(file_path, target_path)
                print(f"[OK] Copied: {meta['OriginalName']}")
                count += 1
            except Exception as e:
                print(f"[Error] Failed to copy {file_path}: {e}")

    print(f"\nProcessing complete. {count} files organized into '{DEST_ROOT}'.")

if __name__ == "__main__":
    main()