import pandas as pd
import json
import glob
import os
import ast

# --- 設定 ---
DATA_ROOT = "analyzed_data/gesture"

def parse_event_data(data_str):
    """EventDataをパース。JSON or Python Dict String"""
    if isinstance(data_str, dict):
        return data_str
    if pd.isna(data_str) or not isinstance(data_str, str):
        return {}
    
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
    # タイムスタンプカラムの確認
    time_col = 'ServerTimestampISO' if 'ServerTimestampISO' in df.columns else 'Timestamp'

    for index, row in df.iterrows():
        # state_change イベントで完了を判定
        if row['EventType'] == 'state_change':
            event_data = parse_event_data(row.get('EventData', '{}'))
            
            # rt_ms (反応時間) があれば試行完了とみなす
            if isinstance(event_data, dict) and 'rt_ms' in event_data:
                rt_ms = event_data['rt_ms']
                
                results.append({
                    'Timestamp': row.get(time_col),
                    'ParticipantID': row.get('ParticipantID', 'Unknown'),
                    'Condition': row.get('Condition', 'Unknown'),
                    'Handedness': row.get('Handedness', 'R'),
                    'TrialID': row.get('TrialID', -1),
                    'TargetGesture': row.get('TargetGesture', 'Unknown'),
                    'TargetID': row.get('TargetID', -1),
                    'ReactionTimeMs': float(rt_ms)
                })

    if not results:
        return None
    return pd.DataFrame(results)

def main():
    if not os.path.exists(DATA_ROOT):
        print(f"Data directory '{DATA_ROOT}' not found. Run organize_logs.py first.")
        return
    
    raw_files = glob.glob(os.path.join(DATA_ROOT, "**", "*_raw.csv"), recursive=True)
    print(f"Found {len(raw_files)} raw gesture logs.")

    total_trials = 0
    for raw_file in raw_files:
        df_summary = process_gesture_raw_log(raw_file)
        if df_summary is not None and not df_summary.empty:
            summary_file = raw_file.replace("_raw.csv", "_summary.csv")
            df_summary.to_csv(summary_file, index=False)
            total_trials += len(df_summary)
            print(f"  -> Processed: {os.path.basename(raw_file)} ({len(df_summary)} trials)")
        else:
            print(f"  -> Skipped: {os.path.basename(raw_file)} (No valid trials)")

    print(f"Gesture analysis complete. Total trials: {total_trials}")

if __name__ == "__main__":
    main()