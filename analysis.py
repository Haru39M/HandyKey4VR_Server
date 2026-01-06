import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
import re

def load_and_process_logs(log_dir="logs_typing"):
    """
    指定されたディレクトリから *_typing.csv を読み込み、結合して返す。
    debugディレクトリは除外する。
    """
    # log_dir直下の *_typing.csv ファイルのみ対象
    files = glob.glob(os.path.join(log_dir, "*_typing.csv"))
    
    if not files:
        print(f"No typing log files found in {log_dir}.")
        return None

    df_list = []
    for f in files:
        try:
            temp_df = pd.read_csv(f)
            df_list.append(temp_df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not df_list:
        return None

    df = pd.concat(df_list, ignore_index=True)

    # --- WPMの再計算 (念のため) ---
    # WPM = (文字数 / 5) / (秒数 / 60)
    if 'CharCount' in df.columns and 'CompletionTime' in df.columns:
        df['WPM'] = (df['CharCount'] / 5) / (df['CompletionTime'] / 60)
    
    return df

def get_practice_count(log_dir, participant_id):
    """
    debugフォルダ内のログから練習回数（最大TrialID）を取得する
    """
    debug_dir = os.path.join(log_dir, "debug")
    if not os.path.exists(debug_dir):
        return 0
        
    # IDを含む *_typing.csv ファイルを検索
    # ファイル名例: log_debug-AM04_..._typing.csv
    pattern = os.path.join(debug_dir, f"*{participant_id}*_typing.csv")
    files = glob.glob(pattern)
    
    if not files:
        return 0
        
    max_trial = 0
    for f in files:
        try:
            df = pd.read_csv(f)
            if 'TrialID' in df.columns and not df.empty:
                local_max = df['TrialID'].max()
                if local_max > max_trial:
                    max_trial = local_max
        except:
            continue
            
    return max_trial

def generate_filename(df, log_dir, test_type="typing"):
    """
    データフレームの内容に基づいてファイル名を生成する
    Format: analysis_<ID>_test_<type>_practice<N>_trial<M>.png
    """
    if df is None or df.empty:
        return "analysis_result.png"

    # ID取得
    if 'ParticipantID' in df.columns:
        ids = df['ParticipantID'].unique()
        # 複数IDがある場合は結合
        id_str = "_".join(map(str, ids)) if len(ids) > 0 else "unknown"
    else:
        id_str = "unknown"
        ids = []

    # 本番回数 (TrialIDの最大値)
    honban_count = df['TrialID'].max() if 'TrialID' in df.columns else 0
    
    # 練習回数 (debugフォルダから取得)
    # 分析対象のID（複数ある場合は先頭）を使って検索
    first_id = ids[0] if len(ids) > 0 else ""
    practice_count = get_practice_count(log_dir, first_id)
    
    base_name = f"analysis_{id_str}_test_{test_type}_practice{practice_count}_trial{honban_count}.png"
    
    # 重複チェックとリネーム
    if not os.path.exists(base_name):
        return base_name
        
    i = 1
    while True:
        name, ext = os.path.splitext(base_name)
        new_name = f"{name}_{i}{ext}"
        if not os.path.exists(new_name):
            return new_name
        i += 1

def plot_results(df, log_dir, test_type="typing"):
    if df is None or df.empty:
        return

    # スタイル設定
    sns.set_style("whitegrid")
    plt.figure(figsize=(12, 6))

    # 学習曲線 (Trial IDごとのWPM推移)
    if 'Condition' in df.columns and 'TrialID' in df.columns and 'WPM' in df.columns:
        sns.lineplot(
            data=df, 
            x="TrialID", 
            y="WPM", 
            hue="Condition", 
            style="Condition", 
            markers=True, 
            dashes=False,
            linewidth=2.5,
            markersize=8
        )

        plt.title(f"Learning Curve: WPM by Trial & Condition ({test_type})", fontsize=16)
        plt.xlabel("Trial ID (Sentence Count)", fontsize=12)
        plt.ylabel("WPM", fontsize=12)
        
        # Y軸の上限設定
        max_wpm = df['WPM'].max() if not df['WPM'].empty else 0
        plt.ylim(0, max_wpm + 10)
        
        plt.legend(title="Condition", fontsize=10, title_fontsize=12)
    
    # ファイル名生成 & 保存
    output_path = generate_filename(df, log_dir, test_type)
    plt.savefig(output_path)
    print(f"Analysis chart saved to {output_path}")
    
    # 統計量の表示
    if 'Condition' in df.columns and 'WPM' in df.columns:
        print(f"\n--- Statistics ({test_type} WPM) ---")
        stats = df.groupby("Condition")["WPM"].agg(['mean', 'std', 'min', 'max', 'count'])
        print(stats)

if __name__ == "__main__":
    # Typing Test Analysis
    log_dir_typing = "logs_typing"
    print(f"Loading Typing logs from {log_dir_typing}...")
    df_typing = load_and_process_logs(log_dir_typing)
    if df_typing is not None:
        plot_results(df_typing, log_dir_typing, "typing")
        # CSV保存も必要ならここに追加
        # df_typing.to_csv(f"analysis_data_typing.csv", index=False)
    else:
        print("No typing logs found.")

    # Gesture Test Analysis (必要に応じて実装)
    # log_dir_gesture = "logs_gesture"
    # ...