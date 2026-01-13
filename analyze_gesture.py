import pandas as pd
import json
import glob
import os
import sys

def parse_event_data(data_str):
    """EventDataカラムのJSON文字列または辞書をパースする"""
    if isinstance(data_str, dict):
        return data_str
    
    if not isinstance(data_str, str):
        return {}

    try:
        # CSV読み込み時に余計な引用符がついている場合の対策
        clean_str = data_str.strip()
        # 文字列が辞書形式ならパース
        return json.loads(clean_str)
    except Exception:
        return {}

def process_raw_log(filepath):
    """RawログからSummaryデータを抽出する"""
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

    results = []

    # 行ごとに処理
    for index, row in df.iterrows():
        # EventDataをパース
        event_data = parse_event_data(row.get('EventData', '{}'))
        
        # 'state_change' イベントで、かつ 'rt_ms' (反応時間) が含まれている行を探す
        # これが試行完了のタイミング
        if row['EventType'] == 'state_change' and isinstance(event_data, dict):
            if 'rt_ms' in event_data:
                results.append({
                    'Timestamp': row['ServerTimestampISO'],
                    'ParticipantID': row['ParticipantID'],
                    'Condition': row['Condition'],
                    'Handedness': row['Handedness'],
                    'TrialID': int(row['TrialID']),
                    'TargetGesture': row['TargetGesture'],
                    'TargetID': row['TargetID'],
                    'ReactionTime': float(event_data['rt_ms'])
                })

    if not results:
        return None
        
    return pd.DataFrame(results)

def main():
    log_dir = "logs_gesture"
    
    # Rawログファイルを再帰的に検索 (debugフォルダなども含む)
    raw_files = glob.glob(os.path.join(log_dir, "**", "*_raw.csv"), recursive=True)
    
    if not raw_files:
        print(f"No raw log files found in {log_dir}.")
        return

    print(f"Found {len(raw_files)} raw log files.")

    count = 0
    for raw_file in raw_files:
        print(f"Processing: {raw_file}")
        df_summary = process_raw_log(raw_file)
        
        if df_summary is not None and not df_summary.empty:
            # Summaryファイル名生成 (_raw.csv -> _summary.csv)
            summary_file = raw_file.replace("_raw.csv", "_summary.csv")
            
            try:
                df_summary.to_csv(summary_file, index=False, encoding='utf-8')
                print(f"  -> Generated: {summary_file} ({len(df_summary)} trials)")
                count += 1
            except Exception as e:
                print(f"  -> Error saving summary: {e}")
        else:
            print("  -> No valid trial data found (skipped).")

    print(f"\nProcessing complete. Generated {count} summary files.")

if __name__ == "__main__":
    main()