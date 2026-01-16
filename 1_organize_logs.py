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
    debugが含まれる場合は練習用として扱う
    """
    basename = os.path.basename(filename)
    name_body = basename.replace(".csv", "")
    parts = name_body.split('_')
    
    # 最小限の要素数チェック
    if len(parts) >= 5 and parts[-1] == "raw":
        type_str = parts[-2] # gesture or typing
        # PIDは通常 parts[1] だが、ファイル名構造に依存
        pid = parts[1]

        if type_str not in ["gesture", "typing"]:
            return None
        
        # 練習モード判定: ファイル名に "debug" が含まれているか
        is_practice = "debug" in basename

        meta = {
            "ParticipantID": pid,
            "Type": type_str,
            "IsPractice": is_practice,
            "OriginalName": basename
        }
        return meta
        
    return None

def main():
    # --- 重要: 既存の分析フォルダをリセットして混入を防ぐ ---
    if os.path.exists(DEST_ROOT):
        print(f"Cleaning up existing '{DEST_ROOT}' directory...")
        try:
            shutil.rmtree(DEST_ROOT)
        except Exception as e:
            print(f"Error removing {DEST_ROOT}: {e}")
            print("Please manually delete the 'analyzed_data' folder and run again.")
            sys.exit(1)
            
    print(f"Scanning for log files in '{SOURCE_ROOT}'...")
    
    files = glob.glob(os.path.join(SOURCE_ROOT, "**", "*_raw.csv"), recursive=True)
    
    count = 0
    for file_path in files:
        # 整理済みフォルダ自身はスキップ（念のため）
        if "analyzed_data" in os.path.abspath(file_path):
            continue

        meta = parse_filename(file_path)
        
        if meta:
            # フォルダ名の決定
            # 本番: analyzed_data/typing/{PID}
            # 練習: analyzed_data/typing_practice/{PID}
            type_dir = meta["Type"]
            if meta["IsPractice"]:
                type_dir += "_practice"
            
            target_dir = os.path.join(DEST_ROOT, type_dir, meta["ParticipantID"])
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
                
            target_path = os.path.join(target_dir, meta["OriginalName"])
            
            try:
                shutil.copy2(file_path, target_path)
                print(f"[OK] Copied: {meta['OriginalName']} -> {type_dir}")
                count += 1
            except Exception as e:
                print(f"[Error] Failed to copy {file_path}: {e}")

    print(f"\nProcessing complete. {count} files organized into '{DEST_ROOT}'.")

if __name__ == "__main__":
    main()