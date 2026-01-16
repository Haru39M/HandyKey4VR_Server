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

    # タイムスタンプパース
    time_col = 'Timestamp' if 'Timestamp' in df.columns else 'ServerTimestampISO'
    if time_col not in df.columns: return None
    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    
    if 'TrialID' not in df.columns: return None
    
    results = []
    
    # TrialIDごとに処理 (NaNを除外してユニークなIDを取得)
    df = df.dropna(subset=['TrialID'])
    trials = df['TrialID'].unique()

    for trial_id in trials:
        trial_data = df[df['TrialID'] == trial_id].sort_values(by=time_col)
        if trial_data.empty: continue

        # --- 1. 完了判定と終了時刻 ---
        completed_events = trial_data[trial_data['EventType'] == 'phrase_completed']
        
        if completed_events.empty:
            # 救済措置
            confirm_events = trial_data[trial_data['EventType'] == 'confirm']
            if confirm_events.empty:
                continue
            end_time = confirm_events.iloc[-1][time_col]
        else:
            end_time = completed_events.iloc[0][time_col]

        # --- 2. InputPhrase の復元 ---
        confirm_events = trial_data[trial_data['EventType'] == 'confirm']
        words = []
        for _, row in confirm_events.iterrows():
            event_data = safe_eval_event_data(row['EventData'])
            word = str(event_data.get('word', ''))
            if word:
                words.append(word)
        
        input_phrase = " ".join(words)

        # --- 3. TargetPhrase の取得 (ロジック強化) ---
        phrase_id = -1
        
        # A. test_started イベントが持つ PhraseID を最優先
        start_events = trial_data[trial_data['EventType'] == 'test_started']
        if not start_events.empty and 'PhraseID' in start_events.columns:
            pid_cand = start_events.iloc[0]['PhraseID']
            if pd.notna(pid_cand):
                phrase_id = int(pid_cand)
        
        # B. なければ最頻値
        if phrase_id == -1 and 'PhraseID' in trial_data.columns:
            valid_pids = trial_data['PhraseID'].dropna()
            if not valid_pids.empty:
                phrase_id = int(valid_pids.mode()[0])

        target_phrase = ""
        if phrases and 0 <= phrase_id < len(phrases):
            target_phrase = phrases[phrase_id]

        # --- 4. 開始時刻とDuration ---
        user_actions = trial_data[~trial_data['EventType'].isin(['system', 'test_started', 'phrase_completed', 'next_phrase_clicked'])]
        
        if not user_actions.empty:
            start_time = user_actions.iloc[0][time_col]
        else:
            continue
            
        duration_sec = (end_time - start_time).total_seconds()
        if duration_sec <= 0: duration_sec = 0.1

        # --- 5. 指標計算 ---
        
        input_char_count = len(input_phrase) # T
        target_char_count = len(target_phrase)

        # WPM (WPM = (|T|-1) / S * 60 / 5)
        wpm_char_count = max(0, input_char_count - 1)
        wpm = (wpm_char_count / 5.0) / (duration_sec / 60.0)
        
        # CER (小文字化して比較)
        # システム仕様上、TargetとInputは一致するはずなので、これでほぼ0になるはず
        error_dist = levenshtein_distance(target_phrase.lower(), input_phrase.lower())
        cer = error_dist / target_char_count if target_char_count > 0 else 0.0
        
        # KSPC
        keystrokes = len(trial_data[trial_data['EventType'].isin(['keydown', 'nav'])])
        kspc = keystrokes / input_char_count if input_char_count > 0 else 0.0

        # Backspace
        bs_count = 0
        keydowns = trial_data[trial_data['EventType'] == 'keydown']
        for _, row in keydowns.iterrows():
            ed = safe_eval_event_data(row['EventData'])
            if ed.get('key') == 'Backspace' or ed.get('code') == 'Backspace':
                bs_count += 1

        # メタデータ
        first_row = trial_data.iloc[0]
        pid = first_row.get('ParticipantID')
        cond = first_row.get('Condition')
        hand = first_row.get('Handedness')
        
        if pd.isna(pid): pid = trial_data['ParticipantID'].dropna().iloc[0] if not trial_data['ParticipantID'].dropna().empty else 'Unknown'
        if pd.isna(cond): cond = trial_data['Condition'].dropna().iloc[0] if not trial_data['Condition'].dropna().empty else 'Unknown'

        # カラム順序
        results.append({
            'ParticipantID': pid,
            'Condition': cond,
            'Handedness': hand,
            'TrialID': int(trial_id),
            'PhraseID': phrase_id,
            'TargetPhrase': target_phrase,
            'InputPhrase': input_phrase,
            # 詳細
            'TargetCharCount': target_char_count,
            'InputCharCount': input_char_count,
            'DurationSec': duration_sec,
            'LevenshteinDist': error_dist,
            'TotalKeystrokes': keystrokes,
            # 主要指標
            'WPM': wpm,
            'CER': cer,
            'KSPC': kspc,
            'BackspaceCount': bs_count
        })

    cols_order = [
        'ParticipantID', 'Condition', 'Handedness', 'TrialID', 'PhraseID',
        'TargetPhrase', 'InputPhrase',
        'TargetCharCount', 'InputCharCount', 'DurationSec', 'LevenshteinDist', 'TotalKeystrokes',
        'WPM', 'CER', 'KSPC', 'BackspaceCount'
    ]
    
    df_ret = pd.DataFrame(results)
    existing_cols = [c for c in cols_order if c in df_ret.columns]
    return df_ret[existing_cols]


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
        else:
            print(f"  -> Skipped (No valid trials): {os.path.basename(raw_file)}")
            
    print(f"Typing analysis complete. Total trials: {total}")

if __name__ == "__main__":
    main()