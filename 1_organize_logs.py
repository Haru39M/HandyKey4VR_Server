import os
import shutil
import glob

# --- 設定 ---
# ログファイルを探すルートディレクトリ
SOURCE_ROOT = "." 
# 整理したログの保存先
DEST_ROOT = "analyzed_data"

def parse_filename(filename):
    """
    ファイル名からメタデータを抽出する
    対応形式: log_{ParticipantID}_{DateTime}_{Type}_raw.csv
    例: log_HW04_2026-01-16-23-37-38_gesture_raw.csv
    """
    basename = os.path.basename(filename)
    name_body = basename.replace(".csv", "")
    parts = name_body.split('_')
    
    # 基本構造: ['log', 'PID', 'DateTime', 'Type', 'raw'] -> 5要素
    if len(parts) >= 5 and parts[-1] == "raw":
        type_str = parts[-2] # gesture or typing
        pid = parts[1]       # ParticipantID
        
        # Typeチェック
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
    
    files = glob.glob(os.path.join(SOURCE_ROOT, "**", "*_raw.csv"), recursive=True)
    
    count = 0
    for file_path in files:
        # 整理済みフォルダ自身はスキップ
        if os.path.abspath(file_path).startswith(os.path.abspath(DEST_ROOT)):
            continue

        meta = parse_filename(file_path)
        
        if meta:
            # analyzed_data/{typing|gesture}/{ParticipantID}/
            target_dir = os.path.join(DEST_ROOT, meta["Type"], meta["ParticipantID"])
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
                
            target_path = os.path.join(target_dir, meta["OriginalName"])
            
            try:
                shutil.copy2(file_path, target_path)
                print(f"[OK] Copied: {meta['OriginalName']} -> {target_dir}")
                count += 1
            except Exception as e:
                print(f"[Error] Failed to copy {file_path}: {e}")

    print(f"\nProcessing complete. {count} files organized into '{DEST_ROOT}'.")

if __name__ == "__main__":
    main()