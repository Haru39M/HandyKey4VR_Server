import pandas as pd
import glob
import os
import ast
import re

# --- 設定 ---
DATA_ROOT = "analyzed_data/typing"
PHRASE_FILE = "phrases2.txt"

def load_phrases(filename=PHRASE_FILE):
    try:
        # カレントまたは親ディレクトリを探索
        if not os.path.exists(filename):
            if os.path.exists(os.path.join("..", filename)):
                filename = os.path.join("..", filename)
            else:
                return []
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            # [source: ...] タグを除去
            content_cleaned = re.sub(r'\[source:\s*\d+\]', '', content)
            phrases = [line.strip() for line in content_cleaned.split('\n') if line.strip()]
        return phrases
    except Exception:
        return []

def levenshtein_distance(s1, s2):
    """編集距離 (CER計算用)"""
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
    if pd.isna(data_str) or not isinstance(data_str, str):
        return {}
    try:
        return ast.literal_eval(data_str)
    except (ValueError, SyntaxError):
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

    # タイムスタンプ
    time_col = 'Timestamp' if 'Timestamp' in df.columns else 'ServerTimestampISO'
    if time_col not in df.columns: return None
    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    
    if 'TrialID' not in df.columns: return None
    
    results = []
    trials = df[df['TrialID'].notna()]['TrialID'].unique()

    for trial_id in trials:
        trial_data = df[df['TrialID'] == trial_id].sort_values(by=time_col)
        if trial_data.empty: continue

        # 完了確認
        confirm_events = trial_data[trial_data['EventType'] == 'confirm']
        if confirm_events.empty: continue
            
        confirm_row = confirm_events.iloc[-1]
        event_data = safe_eval_event_data(confirm_row['EventData'])
        input_phrase = str(event_data.get('word', ''))
        
        first_row = trial_data.iloc[0]
        phrase_id = int(first_row['PhraseID']) if pd.notna(first_row.get('PhraseID')) else -1
        target_phrase = phrases[phrase_id] if (phrases and 0 <= phrase_id < len(phrases)) else ""
        
        # 時間計算
        user_actions = trial_data[~trial_data['EventType'].isin(['system'])]
        start_time = user_actions.iloc[0][time_col] if not user_actions.empty else trial_data.iloc[0][time_col]
        end_time = confirm_row[time_col]
        
        duration_sec = (end_time - start_time).total_seconds()
        if duration_sec <= 0: duration_sec = 0.1

        # --- 指標計算 ---
        
        # 1. WPM
        char_count = len(input_phrase)
        wpm = (char_count / 5.0) / (duration_sec / 60.0)
        
        # 2. CER (Character Error Rate)
        error_dist = levenshtein_distance(target_phrase, input_phrase)
        # ターゲット長が0の場合はCER計算不可(便宜上0または1)
        cer = error_dist / len(target_phrase) if len(target_phrase) > 0 else 0.0
        
        # 3. KSPC (Keystrokes Per Character) - 新規追加
        # 入力効率の指標。1.0に近いほど理想的（誤り訂正が少ない）。
        # 'keydown' イベントの総数をカウント
        total_keystrokes = len(trial_data[trial_data['EventType'] == 'keydown'])
        kspc = total_keystrokes / len(input_phrase) if len(input_phrase) > 0 else 0.0

        # 4. Backspace Count
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
            'KSPC': kspc, # 追加
            'BackspaceCount': bs_count
        })

    return pd.DataFrame(results)

def main():
    if not os.path.exists(DATA_ROOT):
        print(f"Data directory '{DATA_ROOT}' not found. Run 1_organize_logs.py first.")
        return

    phrases = load_phrases()
    raw_files = glob.glob(os.path.join(DATA_ROOT, "**", "*_raw.csv"), recursive=True)
    print(f"Found {len(raw_files)} raw typing logs.")

    total = 0
    for raw_file in raw_files:
        df = process_typing_raw_log(raw_file, phrases)
        if df is not None and not df.empty:
            summary_path = raw_file.replace("_raw.csv", "_summary.csv")
            df.to_csv(summary_path, index=False)
            total += len(df)
            print(f"  -> Processed: {os.path.basename(raw_file)} ({len(df)} trials)")
    print(f"Typing analysis complete. Total: {total}")

if __name__ == "__main__":
    main()