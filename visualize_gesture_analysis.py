import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os

# --- 設定 ---
OUTPUT_DIR = "analyze"

# グラフの色定義 (Condition名に合わせてカスタマイズしてください)
PALETTE = {
    "Keyboard": "#333333",
    "Controller": "#007bff",  # 青
    "Proposed": "#35dc67"     # 緑
}

def load_summary_logs(log_dir="logs_gesture"):
    """logs_gesture以下のすべての_summary.csvを読み込んで結合する"""
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

def plot_rt_by_gesture(df):
    """ジェスチャごとの反応時間 (箱ひげ図)"""
    plt.figure(figsize=(12, 6))
    sns.set_style("whitegrid")

    # TargetGesture順にソートしたい場合は order を指定
    # order = sorted(df['TargetGesture'].unique())

    sns.boxplot(
        data=df,
        x="TargetGesture",
        y="ReactionTime",
        hue="Condition",
        palette=PALETTE,
        showfliers=False # 外れ値を非表示にする場合
    )
    
    # データ点のプロット（分布が見えるように）
    sns.stripplot(
        data=df,
        x="TargetGesture",
        y="ReactionTime",
        hue="Condition",
        dodge=True,
        color='black',
        alpha=0.3,
        jitter=True,
        legend=False
    )

    plt.title("Reaction Time by Gesture Type", fontsize=16)
    plt.ylabel("Reaction Time (ms)", fontsize=12)
    plt.xlabel("Gesture", fontsize=12)
    plt.ylim(0, None) # 0msから開始
    plt.legend(title="Condition", loc='upper right')

    output_path = os.path.join(OUTPUT_DIR, "gesture_rt_boxplot.png")
    plt.savefig(output_path)
    print(f"Saved: {output_path}")
    plt.close()

def plot_rt_learning_curve(df):
    """試行回数ごとの学習曲線 (折れ線グラフ)"""
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")

    # TrialIDごとのRT平均推移
    sns.lineplot(
        data=df,
        x="TrialID",
        y="ReactionTime",
        hue="Condition",
        palette=PALETTE,
        marker="o",
        err_style="band" # 信頼区間を表示
    )

    plt.title("Learning Curve (Reaction Time)", fontsize=16)
    plt.ylabel("Reaction Time (ms)", fontsize=12)
    plt.xlabel("Trial ID", fontsize=12)
    plt.ylim(0, None)
    
    # X軸を整数目盛りにする
    if not df.empty:
        max_trial = df["TrialID"].max()
        plt.xticks(range(1, int(max_trial) + 1))

    output_path = os.path.join(OUTPUT_DIR, "gesture_learning_curve.png")
    plt.savefig(output_path)
    print(f"Saved: {output_path}")
    plt.close()

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("Loading gesture summary logs...")
    df = load_summary_logs()
    
    if df is None or df.empty:
        print("No data available for visualization.")
        return

    print(f"Loaded {len(df)} trials from summary logs.")
    
    # 全体の統計を表示
    print("\n--- Overall Statistics (Reaction Time ms) ---")
    print(df.groupby("Condition")["ReactionTime"].describe().round(2))

    # グラフ描画
    print("\nGenerating plots...")
    plot_rt_by_gesture(df)
    plot_rt_learning_curve(df)
    print("Done.")

if __name__ == "__main__":
    main()