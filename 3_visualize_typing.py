import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DATA_ROOT = "analyzed_data/typing"
JST = timezone(timedelta(hours=+9), 'JST')

# グラフの色定義 (論文用に視認性の高い色)
PALETTE = {
    "Keyboard": "#333333",    # Dark Grey
    "Controller": "#007bff",  # Blue
    "Proposed": "#35dc67"     # Green
}

def get_output_dir():
    # 上書き防止 & タイムゾーンJST
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("analysis_results", timestamp, "typing")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def save_plot(filename, output_dir):
    """PNG, SVG, PDF形式で保存する"""
    base_path = os.path.join(output_dir, filename)
    plt.savefig(base_path + ".png", dpi=300, bbox_inches='tight')
    plt.savefig(base_path + ".svg", format='svg', bbox_inches='tight')
    plt.savefig(base_path + ".pdf", format='pdf', bbox_inches='tight')
    print(f"Saved: {filename} (.png, .svg, .pdf)")
    plt.close()

def load_all_summaries(root_dir):
    files = glob.glob(os.path.join(root_dir, "**", "*_summary.csv"), recursive=True)
    if not files: return None
    df_list = [pd.read_csv(f) for f in files if os.path.getsize(f) > 0]
    if not df_list: return None
    
    df = pd.concat(df_list, ignore_index=True)
    
    # --- データ型変換 (ここがCER可視化修正の肝) ---
    numeric_cols = ['WPM', 'CER', 'KSPC', 'DurationSec', 'TrialID']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

def main():
    output_dir = get_output_dir()
    print(f"Typing graphs will be saved to: {output_dir}")

    df = load_all_summaries(DATA_ROOT)
    if df is None or df.empty:
        print("No typing summary data found.")
        return

    # グローバルなフォント設定（論文用）
    plt.rcParams['font.family'] = 'sans-serif' # 必要に応じて 'Times New Roman' 等に変更
    plt.rcParams['font.size'] = 12

    # 1. WPM Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="WPM", palette=PALETTE, hue="Condition", legend=False)
    plt.title("WPM by Condition")
    save_plot("typing_wpm_boxplot", output_dir)

    # 2. WPM Learning Curve
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="TrialID", y="WPM", hue="Condition", palette=PALETTE, marker="o", errorbar='sd')
    plt.title("WPM Learning Curve")
    plt.grid(True, linestyle='--', alpha=0.5)
    save_plot("typing_wpm_learning_curve", output_dir)

    # 3. CER Boxplot (修正済み)
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="CER", palette=PALETTE, hue="Condition", legend=False)
    plt.title("Character Error Rate (CER)")
    # ylimを自動設定に変更（白いグラフ問題対策）
    # 極端に大きい外れ値がある場合のみクリップするなどの処理も検討可能
    # plt.ylim(0, 0.5) 
    save_plot("typing_cer_boxplot", output_dir)

    # 4. KSPC Boxplot (新規指標)
    plt.figure(figsize=(8, 6))
    if 'KSPC' in df.columns:
        sns.boxplot(data=df, x="Condition", y="KSPC", palette=PALETTE, hue="Condition", legend=False)
        plt.title("Keystrokes Per Character (KSPC)")
        # 1.0が理想値なので、基準線を引く
        plt.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='Ideal (1.0)')
        plt.legend()
        save_plot("typing_kspc_boxplot", output_dir)

    print("Typing visualization complete.")

if __name__ == "__main__":
    main()