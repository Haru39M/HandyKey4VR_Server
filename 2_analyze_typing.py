import pandas as pd
import glob
import os
import ast
import re

# --- 設定 ---
# 親ディレクトリを指定（typing, typing_practice 両方を探索するため）
DATA_ROOT_BASE = "analyzed_data"
PHRASE_FILE = "phrases2.txt"

def load_phrases(filename=PHRASE_FILE):
    try:
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

    # --- タイムスタンプパース (修正箇所) ---
    # サーバー受信時刻(Timestamp)はバッチ送信時に同時刻になりDurationが0になる恐れがあるため、
    # クライアント発生時刻(ClientTimestamp)があればそれを優先する。
    if 'ClientTimestamp' in df.columns:
        time_col = 'ClientTimestamp'
        # ClientTimestampはミリ秒単位のUNIX時間と想定
        df[time_col] = pd.to_datetime(df[time_col], unit='ms', errors='coerce')
    else:
        # ClientTimestampがない場合は従来のサーバー時刻を使用
        time_col = 'Timestamp' if 'Timestamp' in df.columns else 'ServerTimestampISO'
        if time_col not in df.columns: return None
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    
    if 'TrialID' not in df.columns: return None
    
    results = []
    
    # TrialIDごとに処理
    df = df.dropna(subset=['TrialID'])
    trials = df['TrialID'].unique()

    for trial_id in trials:
        trial_data = df[df['TrialID'] == trial_id].sort_values(by=time_col)
        if trial_data.empty: continue

        # --- 1. 完了判定と終了時刻 ---
        completed_events = trial_data[trial_data['EventType'] == 'phrase_completed']
        
        # confirmイベントを抽出
        confirm_events = trial_data[trial_data['EventType'] == 'confirm']
        
        if completed_events.empty:
            if confirm_events.empty: continue
            end_time = confirm_events.iloc[-1][time_col]
        else:
            end_time = completed_events.iloc[0][time_col]

        # --- 2. 開始時刻とDuration (文全体) ---
        # system系以外の最初のアクション
        user_actions = trial_data[~trial_data['EventType'].isin(['system', 'test_started', 'phrase_completed', 'next_phrase_clicked'])]
        
        if not user_actions.empty:
            start_time = user_actions.iloc[0][time_col]
        else:
            continue
            
        total_duration_sec = (end_time - start_time).total_seconds()
        if total_duration_sec <= 0: total_duration_sec = 0.1

        # --- 3. 単語ごとの分析 (ActiveWPM, MeanWordWPM用) ---
        input_words = []
        word_wpms = []
        active_duration_sum = 0
        
        # 各単語区間の開始点（初期値は試行開始時間）
        last_confirm_time = start_time 
        
        # confirmごとにループ (修正: enumerateを追加)
        for i, (_, row) in enumerate(confirm_events.iterrows()):
            confirm_time = row[time_col]
            event_data = safe_eval_event_data(row['EventData'])
            word = str(event_data.get('word', ''))
            
            if not word: continue
            input_words.append(word)
            
            # --- この単語区間のアクティブ時間計測 ---
            # 区間データ
            segment = trial_data[(trial_data[time_col] > last_confirm_time) & (trial_data[time_col] <= confirm_time)]
            
            # 区間内のユーザー操作
            seg_actions = segment[~segment['EventType'].isin(['system', 'confirm'])]
            
            if not seg_actions.empty:
                # 実際の入力開始時刻
                word_start_time = seg_actions.iloc[0][time_col]
                
                # アイドルを除いた入力時間
                active_dur = (confirm_time - word_start_time).total_seconds()
                
                # 単語全体の所要時間 (アイドル込み)
                full_dur = (confirm_time - last_confirm_time).total_seconds()
                
                if i == 0: full_dur = active_dur # 1単語目は開始時刻＝入力開始時刻とみなす

                # Active時間の積算
                if active_dur > 0:
                    active_duration_sum += active_dur
                
                # 単語WPM
                if full_dur > 0:
                    w_wpm = (len(word) / 5.0) / (full_dur / 60.0)
                    word_wpms.append(w_wpm)
            
            last_confirm_time = confirm_time

        input_phrase = " ".join(input_words)

        # --- 4. TargetPhrase の取得 ---
        phrase_id = -1
        start_events = trial_data[trial_data['EventType'] == 'test_started']
        if not start_events.empty and 'PhraseID' in start_events.columns:
            pid_cand = start_events.iloc[0]['PhraseID']
            if pd.notna(pid_cand): phrase_id = int(pid_cand)
        if phrase_id == -1 and 'PhraseID' in trial_data.columns:
            valid_pids = trial_data['PhraseID'].dropna()
            if not valid_pids.empty: phrase_id = int(valid_pids.mode()[0])

        target_phrase = phrases[phrase_id] if (phrases and 0 <= phrase_id < len(phrases)) else ""

        # --- 5. 指標計算 ---
        
        input_char_count = len(input_phrase)
        target_char_count = len(target_phrase)

        # A. 文全体 WPM (アイドル込み)
        wpm_char_count = max(0, input_char_count - 1)
        wpm = (wpm_char_count / 5.0) / (total_duration_sec / 60.0)
        
        # B. Active WPM (アイドル除外)
        if active_duration_sum > 0:
            active_wpm = (wpm_char_count / 5.0) / (active_duration_sum / 60.0)
        else:
            active_wpm = 0

        # C. Mean Word WPM (単語ごとのWPMの平均)
        if word_wpms:
            mean_word_wpm = sum(word_wpms) / len(word_wpms)
        else:
            mean_word_wpm = 0
        
        # CER
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

        first_row = trial_data.iloc[0]
        pid = first_row.get('ParticipantID')
        cond = first_row.get('Condition')
        hand = first_row.get('Handedness')
        if pd.isna(pid): pid = trial_data['ParticipantID'].dropna().iloc[0] if not trial_data['ParticipantID'].dropna().empty else 'Unknown'
        if pd.isna(cond): cond = trial_data['Condition'].dropna().iloc[0] if not trial_data['Condition'].dropna().empty else 'Unknown'

        results.append({
            'ParticipantID': pid,
            'Condition': cond,
            'Handedness': hand,
            'TrialID': int(trial_id),
            'PhraseID': phrase_id,
            'TargetPhrase': target_phrase,
            'InputPhrase': input_phrase,
            # 詳細情報
            'TargetCharCount': target_char_count,
            'InputCharCount': input_char_count,
            'DurationSec': total_duration_sec,
            'ActiveDurationSec': active_duration_sum,
            'LevenshteinDist': error_dist,
            'TotalKeystrokes': keystrokes,
            # 主要指標
            'WPM': wpm,
            'ActiveWPM': active_wpm,
            'MeanWordWPM': mean_word_wpm,
            'CER': cer,
            'KSPC': kspc,
            'BackspaceCount': bs_count
        })

    # カラム順序
    cols_order = [
        'ParticipantID', 'Condition', 'Handedness', 'TrialID', 'PhraseID',
        'TargetPhrase', 'InputPhrase',
        'TargetCharCount', 'InputCharCount', 
        'DurationSec', 'ActiveDurationSec', 
        'LevenshteinDist', 'TotalKeystrokes',
        'WPM', 'ActiveWPM', 'MeanWordWPM', 
        'CER', 'KSPC', 'BackspaceCount'
    ]
    df_ret = pd.DataFrame(results)
    return df_ret[[c for c in cols_order if c in df_ret.columns]]


def main():
    if not os.path.exists(DATA_ROOT_BASE):
        print(f"Data directory '{DATA_ROOT_BASE}' not found. Run 1_organize_logs.py first.")
        return

    phrases = load_phrases()
    all_raw_files = glob.glob(os.path.join(DATA_ROOT_BASE, "**", "*_raw.csv"), recursive=True)
    raw_files = [f for f in all_raw_files if "typing" in f]

    print(f"Found {len(raw_files)} raw typing logs (including practice).")

    total = 0
    for raw_file in raw_files:
        df = process_typing_raw_log(raw_file, phrases)
        if df is not None and not df.empty:
            summary_path = raw_file.replace("_raw.csv", "_summary.csv")
            df.to_csv(summary_path, index=False)
            total += len(df)
            print(f"  -> Processed: {os.path.basename(raw_file)} ({len(df)} trials)")
        else:
            print(f"  -> Skipped: {os.path.basename(raw_file)}")
            
    print(f"Typing analysis complete. Total trials: {total}")

if __name__ == "__main__":
    main()