import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os

# --- 設定 ---
# グラフの色定義 (固定)
PALETTE = {
    "Keyboard": "#333333",    # 黒/グレー
    "Controller": "#007bff",  # 青
    "Proposed": "#35dc67"     # 赤
}

# グラフ出力先
OUTPUT_DIR = "analyze"

def load_summary_logs(log_dir="logs_typing"):
    """Summaryログを再帰的に読み込んで結合する"""
    files = glob.glob(os.path.join(log_dir, "**", "*_summary.csv"), recursive=True)
    
    if not files:
        print("No summary log files found.")
        return None

    df_list = []
    for f in files:
        try:
            tmp = pd.read_csv(f)
            df_list.append(tmp)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not df_list:
        return None

    return pd.concat(df_list, ignore_index=True)

def plot_wpm_learning_curve(df):
    """WPMの学習曲線を描画"""
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")

    # TrialIDごとのWPM推移 (Conditionで色分け)
    # errorbar='sd' で標準偏差の帯を表示、あるいは 'ci' で信頼区間
    sns.lineplot(
        data=df,
        x="TrialID",
        y="WPM",
        hue="Condition",
        style="Condition",
        palette=PALETTE,
        markers=True,
        dashes=False,
        linewidth=2.5,
        markersize=8
    )

    plt.title("Learning Curve: WPM by Trial", fontsize=16)
    plt.xlabel("Trial ID", fontsize=12)
    plt.ylabel("WPM", fontsize=12)
    plt.legend(title="Condition")
    
    # 軸調整
    plt.ylim(0, max(df["WPM"].max() * 1.1, 10)) # 少し余裕を持たせる
    plt.xticks(sorted(df["TrialID"].unique())) # 整数目盛り

    output_path = os.path.join(OUTPUT_DIR, "wpm_learning_curve.png")
    plt.savefig(output_path)
    print(f"Saved: {output_path}")
    plt.close()

def plot_wpm_boxplot(df):
    """条件ごとのWPM箱ひげ図"""
    plt.figure(figsize=(8, 6))
    
    sns.boxplot(
        data=df,
        x="Condition",
        y="WPM",
        palette=PALETTE,
        order=["Keyboard", "Controller", "Proposed"] # 並び順指定
    )
    
    plt.title("WPM Distribution by Condition", fontsize=16)
    
    output_path = os.path.join(OUTPUT_DIR, "wpm_boxplot.png")
    plt.savefig(output_path)
    print(f"Saved: {output_path}")
    plt.close()

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("Loading summary logs...")
    df = load_summary_logs()
    
    if df is None or df.empty:
        print("No data available for visualization.")
        return

    # データ型の調整
    df["WPM"] = pd.to_numeric(df["WPM"], errors='coerce')
    df = df.dropna(subset=["WPM"]) # WPMが欠損している行は除外

    print(f"Loaded {len(df)} records.")
    print("Generating plots...")

    plot_wpm_learning_curve(df)
    plot_wpm_boxplot(df)
    
    # 統計量出力
    print("\n--- Summary Statistics (WPM) ---")
    print(df.groupby("Condition")["WPM"].describe())

if __name__ == "__main__":
    main()