import pandas as pd
import glob
import os
import ast
import re

# --- 設定 ---
DATA_ROOT = "analyzed_data/typing"
PHRASE_FILE = "phrases2.txt"

def load_phrases(filename=PHRASE_FILE):
    """フレーズリストを読み込む"""
    try:
        # カレントディレクトリまたは親ディレクトリを探す
        if not os.path.exists(filename):
            if os.path.exists(os.path.join("..", filename)):
                filename = os.path.join("..", filename)
            else:
                return []
                
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            content_cleaned = re.sub(r'\[source:\s*\d+\]', '', content)
            phrases = [line.strip() for line in content_cleaned.split('\n') if line.strip()]
        return phrases
    except Exception:
        return []

def levenshtein_distance(s1, s2):
    """編集距離"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def safe_eval_event_data(data_str):
    """EventData (Python dict string or JSON) を安全にパース"""
    if pd.isna(data_str) or not isinstance(data_str, str):
        return {}
    try:
        return ast.literal_eval(data_str)
    except (ValueError, SyntaxError):
        # JSON形式の可能性
        try:
            import json
            return json.loads(data_str)
        except:
            return {}

def process_typing_raw_log(filepath, phrases):
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

    time_col = 'Timestamp' if 'Timestamp' in df.columns else 'ServerTimestampISO'
    if time_col not in df.columns:
        return None
        
    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    
    results = []
    
    # TrialIDでグループ化
    if 'TrialID' not in df.columns:
        return None
        
    trials = df[df['TrialID'].notna()]['TrialID'].unique()

    for trial_id in trials:
        trial_data = df[df['TrialID'] == trial_id].sort_values(by=time_col)
        if trial_data.empty: continue

        first_row = trial_data.iloc[0]
        
        # 完了イベント(confirm)を探す
        confirm_events = trial_data[trial_data['EventType'] == 'confirm']
        if confirm_events.empty:
            continue
            
        confirm_row = confirm_events.iloc[-1]
        event_data = safe_eval_event_data(confirm_row['EventData'])
        input_phrase = event_data.get('word', '')
        
        # ターゲットフレーズ
        phrase_id = int(first_row['PhraseID']) if pd.notna(first_row.get('PhraseID')) else -1
        target_phrase = phrases[phrase_id] if (phrases and 0 <= phrase_id < len(phrases)) else ""
        
        # 時間計算 (systemイベント以外の最初のアクション ~ confirm)
        user_actions = trial_data[~trial_data['EventType'].isin(['system'])]
        if user_actions.empty:
            start_time = trial_data.iloc[0][time_col]
        else:
            start_time = user_actions.iloc[0][time_col]
        
        end_time = confirm_row[time_col]
        duration_sec = (end_time - start_time).total_seconds()
        if duration_sec <= 0: duration_sec = 0.1

        # 指標
        char_count = len(input_phrase)
        wpm = (char_count / 5.0) / (duration_sec / 60.0)
        error_dist = levenshtein_distance(target_phrase, input_phrase)
        cer = error_dist / len(target_phrase) if len(target_phrase) > 0 else 0
        
        # Backspace
        bs_count = 0
        for _, row in trial_data.iterrows():
            if row['EventType'] == 'keydown':
                ed = safe_eval_event_data(row['EventData'])
                if ed.get('key') == 'Backspace':
                    bs_count += 1

        results.append({
            'ParticipantID': first_row.get('ParticipantID', 'Unknown'),
            'Condition': first_row.get('Condition', 'Unknown'),
            'Handedness': first_row.get('Handedness', 'R'),
            'TrialID': trial_id,
            'TargetPhrase': target_phrase,
            'InputPhrase': input_phrase,
            'DurationSec': duration_sec,
            'WPM': wpm,
            'CER': cer,
            'BackspaceCount': bs_count
        })

    return pd.DataFrame(results)

def main():
    if not os.path.exists(DATA_ROOT):
        print(f"Data directory '{DATA_ROOT}' not found. Run organize_logs.py first.")
        return

    phrases = load_phrases()
    if not phrases:
        print("Warning: Phrase file not found or empty.")

    raw_files = glob.glob(os.path.join(DATA_ROOT, "**", "*_raw.csv"), recursive=True)
    print(f"Found {len(raw_files)} raw typing logs.")

    total_trials = 0
    for raw_file in raw_files:
        df_summary = process_typing_raw_log(raw_file, phrases)
        if df_summary is not None and not df_summary.empty:
            summary_file = raw_file.replace("_raw.csv", "_summary.csv")
            df_summary.to_csv(summary_file, index=False)
            total_trials += len(df_summary)
            print(f"  -> Processed: {os.path.basename(raw_file)} ({len(df_summary)} trials)")
        else:
            print(f"  -> Skipped: {os.path.basename(raw_file)} (No valid trials)")

    print(f"Typing analysis complete. Total trials: {total_trials}")

if __name__ == "__main__":
    main()