import pandas as pd
import glob
import os
import ast
import re

def load_phrases(filename='phrases2.txt'):
    """フレーズリストを読み込む"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # [source: ...] などのタグを除去
            content = f.read()
            content_cleaned = re.sub(r'\[source:\s*\d+\]', '', content)
            phrases = [line.strip() for line in content_cleaned.split('\n') if line.strip()]
        return phrases
    except FileNotFoundError:
        print(f"Error: {filename} not found.")
        return []

def levenshtein_distance(s1, s2):
    """編集距離を計算"""
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

def process_raw_log(file_path, phrases):
    """1つのRawログファイルを処理してDataFrameを返す"""
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

    # 必要な列があるか確認
    required_cols = ['TrialID', 'PhraseID', 'EventType', 'EventData', 'ClientTimestamp']
    if not all(col in df.columns for col in required_cols):
        print(f"Skipping {file_path}: Missing columns.")
        return None

    results = []
    
    # メタデータ取得 (最初の行から)
    participant_id = df.iloc[0]['ParticipantID'] if 'ParticipantID' in df.columns else 'Unknown'
    condition = df.iloc[0]['Condition'] if 'Condition' in df.columns else 'Unknown'
    handedness = df.iloc[0]['Handedness'] if 'Handedness' in df.columns else 'R'

    # トライアルごとに処理
    for trial_id, group in df.groupby('TrialID'):
        group = group.sort_values('ClientTimestamp')
        
        # --- ターゲット文の特定 ---
        phrase_id = -1
        
        # 1. keydownイベントのPhraseIDを探す
        keydown_events = group[group['EventType'] == 'keydown']
        if not keydown_events.empty:
            phrase_id = keydown_events.iloc[0]['PhraseID']
        else:
            # 2. keydownがない場合は、最も多く出現するPhraseIDを採用する (Mode)
            try:
                phrase_id = group['PhraseID'].mode()[0]
            except IndexError:
                phrase_id = group.iloc[0]['PhraseID']

        if 0 <= phrase_id < len(phrases):
            target_phrase = phrases[int(phrase_id)]
        else:
            target_phrase = ""

        # 入力文の復元 (confirmイベントをつなげる)
        input_words = []
        backspace_count = 0
        
        for _, row in group.iterrows():
            evt_type = row['EventType']
            evt_data_str = row['EventData']
            
            # EventDataは文字列化された辞書なのでパースする
            try:
                if isinstance(evt_data_str, str) and (evt_data_str.startswith('{') or evt_data_str.startswith('"')):
                    if evt_data_str.startswith('"') and evt_data_str.endswith('"'):
                        evt_data_str = evt_data_str[1:-1]
                    evt_data = ast.literal_eval(evt_data_str)
                else:
                    evt_data = evt_data_str
            except:
                evt_data = {}

            if evt_type == 'confirm':
                if isinstance(evt_data, dict) and 'word' in evt_data:
                    input_words.append(evt_data['word'])
            
            elif evt_type == 'undo':
                if input_words:
                    input_words.pop()
            
            elif evt_type == 'keydown':
                # Backspaceカウント
                if isinstance(evt_data, dict) and evt_data.get('key') == 'Backspace':
                    backspace_count += 1
                elif isinstance(evt_data, str) and evt_data == 'Backspace':
                    backspace_count += 1

        input_phrase = " ".join(input_words)
        
        # --- 修正: 入力文が空の場合はスキップ (未完了または開始直後のデータ) ---
        if not input_phrase:
            continue

        # --- 時間計算 ---
        # 終了時刻: このTrialの最後のイベント時刻
        end_time = group['ClientTimestamp'].max()
        
        # 開始時刻: そのTrialの最初のイベント時刻
        start_time = group['ClientTimestamp'].min()
        
        # Trial 1 で system: test_started があればそれを使う
        start_evts = group[group['EventData'].astype(str).str.contains('test_started', na=False)]
        if not start_evts.empty:
            start_time = start_evts.iloc[0]['ClientTimestamp']
        
        # ミリ秒 -> 秒
        duration = (end_time - start_time) / 1000.0
        if duration <= 0: duration = 0.001

        # 指標計算
        char_count = len(input_phrase)
        # WPM = (文字数 / 5) / (分)
        wpm = (char_count / 5.0) / (duration / 60.0)
        
        error_dist = levenshtein_distance(target_phrase, input_phrase)
        
        # 結果格納
        results.append({
            'Timestamp': group.iloc[-1]['Timestamp'], # 完了時のサーバー時刻
            'ParticipantID': participant_id,
            'Condition': condition,
            'Handedness': handedness,
            'TrialID': trial_id,
            'TargetPhrase': target_phrase,
            'InputPhrase': input_phrase,
            'CompletionTime': round(duration, 3),
            'CharCount': char_count,
            'WPM': round(wpm, 2),
            'ErrorDist': error_dist,
            'BackspaceCount': backspace_count
        })

    return pd.DataFrame(results)

def main():
    log_dir = "logs_typing"
    phrases = load_phrases()
    
    if not phrases:
        print("Phrases not found. Aborting.")
        return

    # Rawログファイルを検索 (debugフォルダ含む)
    raw_files = glob.glob(os.path.join(log_dir, "**", "*_raw.csv"), recursive=True)
    
    if not raw_files:
        print("No raw log files found.")
        return

    print(f"Found {len(raw_files)} raw log files.")

    for raw_file in raw_files:
        print(f"Processing: {raw_file}")
        df_summary = process_raw_log(raw_file, phrases)
        
        if df_summary is not None and not df_summary.empty:
            # 保存ファイル名生成 (_raw.csv -> _summary.csv)
            summary_file = raw_file.replace("_raw.csv", "_summary.csv")
            
            # CSV保存
            df_summary.to_csv(summary_file, index=False, encoding='utf-8')
            print(f"  -> Saved summary to: {summary_file}")
        else:
            print("  -> Skipped (No valid data)")

if __name__ == "__main__":
    main()