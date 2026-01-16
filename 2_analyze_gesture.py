import pandas as pd
import json
import glob
import os
import ast

# --- 設定 ---
# 親ディレクトリ指定
DATA_ROOT_BASE = "analyzed_data"

def parse_event_data(data_str):
    if isinstance(data_str, dict): return data_str
    if pd.isna(data_str) or not isinstance(data_str, str): return {}
    clean_str = data_str.strip()
    try:
        return json.loads(clean_str)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(clean_str)
        except:
            return {}

def process_gesture_raw_log(filepath):
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

    results = []
    time_col = 'ServerTimestampISO' if 'ServerTimestampISO' in df.columns else 'Timestamp'

    for index, row in df.iterrows():
        if row['EventType'] == 'state_change':
            event_data = parse_event_data(row.get('EventData', '{}'))
            if isinstance(event_data, dict) and 'rt_ms' in event_data:
                results.append({
                    'Timestamp': row.get(time_col),
                    'ParticipantID': row.get('ParticipantID', 'Unknown'),
                    'Condition': row.get('Condition', 'Unknown'),
                    'Handedness': row.get('Handedness', 'R'),
                    'TrialID': row.get('TrialID', -1),
                    'TargetGesture': row.get('TargetGesture', 'Unknown'),
                    'TargetID': row.get('TargetID', -1),
                    'ReactionTimeMs': float(event_data['rt_ms'])
                })

    if not results: return None
    return pd.DataFrame(results)

def main():
    if not os.path.exists(DATA_ROOT_BASE):
        print(f"Data directory '{DATA_ROOT_BASE}' not found. Run 1_organize_logs.py first.")
        return
    
    # "gesture" という文字が含まれるパスのみ対象 (gesture, gesture_practice)
    all_raw_files = glob.glob(os.path.join(DATA_ROOT_BASE, "**", "*_raw.csv"), recursive=True)
    raw_files = [f for f in all_raw_files if "gesture" in f]
    
    print(f"Found {len(raw_files)} raw gesture logs (including practice).")

    total = 0
    for raw_file in raw_files:
        df = process_gesture_raw_log(raw_file)
        if df is not None and not df.empty:
            df.to_csv(raw_file.replace("_raw.csv", "_summary.csv"), index=False)
            total += len(df)
            print(f"  -> Processed: {os.path.basename(raw_file)} ({len(df)} trials)")
    print(f"Gesture analysis complete. Total: {total}")

if __name__ == "__main__":
    main()