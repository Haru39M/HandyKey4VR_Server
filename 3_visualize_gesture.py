import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
from datetime import datetime

# --- 設定 ---
DATA_ROOT = "analyzed_data/gesture"

PALETTE = {
    "Keyboard": "#333333",
    "Controller": "#007bff",
    "Proposed": "#35dc67"
}

def get_output_dir():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("analysis_results", timestamp, "gesture")
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
    print(f"Gesture graphs will be saved to: {output_dir}")

    df = load_all_summaries(DATA_ROOT)
    if df is None or df.empty:
        print("No gesture summary data found.")
        return

    # Reaction Time Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="ReactionTimeMs", palette=PALETTE, hue="Condition", legend=False)
    plt.title("Gesture Reaction Time by Condition")
    plt.ylabel("Time (ms)")
    plt.savefig(os.path.join(output_dir, "gesture_rt_boxplot.png"))
    plt.close()

    # Learning Curve (新規追加)
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="TrialID", y="ReactionTimeMs", hue="Condition", palette=PALETTE, marker="o")
    plt.title("Gesture Reaction Time Learning Curve")
    plt.ylabel("Time (ms)")
    plt.xlabel("Trial ID")
    plt.grid(True, linestyle='--', alpha=0.5)
    # X軸を整数に強制（試行回数が少ない場合見やすくするため）
    if not df.empty:
        max_trial = int(df["TrialID"].max())
        step = max(1, max_trial // 10)
        plt.xticks(range(1, max_trial + 1, step))
    plt.savefig(os.path.join(output_dir, "gesture_learning_curve.png"))
    plt.close()
    
    # By Gesture Type
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df, x="TargetGesture", y="ReactionTimeMs", hue="Condition", palette=PALETTE)
    plt.title("Reaction Time by Gesture Type")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "gesture_rt_by_type.png"))
    plt.close()

    print("Gesture visualization complete.")

if __name__ == "__main__":
    main()