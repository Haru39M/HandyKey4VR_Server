import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
from datetime import datetime

# --- 設定 ---
DATA_ROOT = "analyzed_data/typing"

# グラフの色定義
PALETTE = {
    "Keyboard": "#333333",
    "Controller": "#007bff",
    "Proposed": "#35dc67"
}

def get_output_dir():
    # 上書き防止のため日時つきフォルダを作成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("analysis_results", timestamp, "typing")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def load_all_summaries(root_dir):
    files = glob.glob(os.path.join(root_dir, "**", "*_summary.csv"), recursive=True)
    if not files: return None
    df_list = [pd.read_csv(f) for f in files if os.path.getsize(f) > 0]
    if not df_list: return None
    return pd.concat(df_list, ignore_index=True)

def main():
    output_dir = get_output_dir()
    print(f"Typing graphs will be saved to: {output_dir}")

    df = load_all_summaries(DATA_ROOT)
    if df is None or df.empty:
        print("No typing summary data found.")
        return

    # WPM Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="WPM", palette=PALETTE, hue="Condition", legend=False)
    plt.title("WPM by Condition")
    plt.savefig(os.path.join(output_dir, "typing_wpm_boxplot.png"))
    plt.close()

    # Learning Curve
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="TrialID", y="WPM", hue="Condition", palette=PALETTE, marker="o")
    plt.title("WPM Learning Curve")
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.savefig(os.path.join(output_dir, "typing_wpm_learning_curve.png"))
    plt.close()

    # CER Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="CER", palette=PALETTE, hue="Condition", legend=False)
    plt.title("CER by Condition")
    plt.ylim(0, 0.5)
    plt.savefig(os.path.join(output_dir, "typing_cer_boxplot.png"))
    plt.close()

    print("Typing visualization complete.")

if __name__ == "__main__":
    main()