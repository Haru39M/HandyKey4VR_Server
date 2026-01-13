import pandas as pd
import json
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys

def parse_event_data(row):
    """EventDataカラムのJSON文字列をパースして辞書にする"""
    try:
        data_str = row['EventData']
        if isinstance(data_str, str):
            # CSVの仕様で二重引用符などが含まれる場合があるためjson.loadsを試みる
            return json.loads(data_str)
        return data_str
    except:
        return {}

def analyze_gesture_log(file_path):
    print(f"Loading log file: {file_path}")
    
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # EventDataをパースして辞書列を追加
    df['EventDataDict'] = df.apply(parse_event_data, axis=1)

    # 反応時間 (rt_ms) が含まれる行（試行完了ログ）を抽出
    # 条件: EventTypeが'state_change' かつ rt_ms キーを持っている
    results = []
    
    for index, row in df.iterrows():
        data = row['EventDataDict']
        if row['EventType'] == 'state_change' and isinstance(data, dict):
            if 'rt_ms' in data:
                results.append({
                    'TrialID': row['TrialID'],
                    'ParticipantID': row['ParticipantID'],
                    'Condition': row['Condition'],
                    'TargetGesture': row['TargetGesture'],
                    'RT_ms': data['rt_ms']
                })

    if not results:
        print("No reaction time data found in this log.")
        return

    res_df = pd.read_json(json.dumps(results))
    
    print("\n--- Analysis Result ---")
    print(f"Total Trials: {len(res_df)}")
    
    # 1. ジェスチャごとの統計
    print("\n[Statistics by Gesture]")
    stats_gesture = res_df.groupby('TargetGesture')['RT_ms'].agg(['count', 'mean', 'std', 'min', 'max'])
    print(stats_gesture.round(2))

    # 2. 全体の平均
    mean_rt = res_df['RT_ms'].mean()
    print(f"\nOverall Mean RT: {mean_rt:.2f} ms")

    # --- 可視化 (Boxplot) ---
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")
    
    # ジェスチャごとの箱ひげ図
    sns.boxplot(x='TargetGesture', y='RT_ms', data=res_df, hue='TargetGesture', palette="Set2", legend=False)
    sns.stripplot(x='TargetGesture', y='RT_ms', data=res_df, color='black', alpha=0.5, jitter=True)
    
    plt.title('Reaction Time by Gesture')
    plt.ylabel('Reaction Time (ms)')
    plt.xlabel('Gesture Type')
    plt.ylim(0, None) # 0から開始
    
    # 保存または表示
    output_img = file_path.replace('.csv', '_analysis.png')
    plt.savefig(output_img)
    print(f"\nGraph saved to: {output_img}")
    # plt.show() # 実行環境でGUIが使えるならコメントアウトを外す

if __name__ == "__main__":
    # 解析したいログファイルを指定
    # 最新のログファイルを自動で探すか、引数で指定
    target_file = "logs_gesture/debug/log_debug-p01_2026-01-13-16-01-55_gesture_raw.csv"
    
    # コマンドライン引数があればそれを使う
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
        
    if os.path.exists(target_file):
        analyze_gesture_log(target_file)
    else:
        # 見つからない場合はカレントディレクトリのCSVを探す例
        csvs = [f for f in os.listdir('.') if f.endswith('.csv') and 'gesture' in f]
        if csvs:
            analyze_gesture_log(csvs[0])
        else:
            print(f"File not found: {target_file}")