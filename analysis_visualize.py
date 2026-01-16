import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
from datetime import datetime

# --- 設定 ---
TYPING_DATA_ROOT = "analyzed_data/typing"
GESTURE_DATA_ROOT = "analyzed_data/gesture"

PALETTE = {
    "Keyboard": "#333333",
    "Controller": "#007bff",
    "Proposed": "#35dc67"
}

def get_output_dir():
    # 上書き防止のため日時つきフォルダを作成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("analysis_results", timestamp)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def load_all_summaries(root_dir):
    files = glob.glob(os.path.join(root_dir, "**", "*_summary.csv"), recursive=True)
    if not files: return None
    
    df_list = []
    for f in files:
        try:
            df_list.append(pd.read_csv(f))
        except: pass
            
    if not df_list: return None
    return pd.concat(df_list, ignore_index=True)

def plot_typing(df, output_dir):
    # WPM Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="WPM", palette=PALETTE, hue="Condition", legend=False)
    plt.title("WPM by Condition")
    plt.savefig(os.path.join(output_dir, "typing_wpm_boxplot.png"))
    plt.close()

    # Learning Curve
    plt.figure(figsize=(10, 6))
    # lineplotはデフォルトでmeanとconfidence intervalを描画
    sns.lineplot(data=df, x="TrialID", y="WPM", hue="Condition", palette=PALETTE, marker="o")
    plt.title("WPM Learning Curve")
    plt.savefig(os.path.join(output_dir, "typing_wpm_learning_curve.png"))
    plt.close()

    # CER Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="CER", palette=PALETTE, hue="Condition", legend=False)
    plt.title("CER by Condition")
    plt.ylim(0, 0.5)
    plt.savefig(os.path.join(output_dir, "typing_cer_boxplot.png"))
    plt.close()

def plot_gesture(df, output_dir):
    # Reaction Time Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="ReactionTimeMs", palette=PALETTE, hue="Condition", legend=False)
    plt.title("Gesture Reaction Time")
    plt.ylabel("Time (ms)")
    plt.savefig(os.path.join(output_dir, "gesture_rt_boxplot.png"))
    plt.close()
    
    # By Gesture Type
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df, x="TargetGesture", y="ReactionTimeMs", hue="Condition", palette=PALETTE)
    plt.title("Reaction Time by Gesture Type")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "gesture_rt_by_type.png"))
    plt.close()

def main():
    output_dir = get_output_dir()
    print(f"Output directory: {output_dir}")

    # Typing
    df_typing = load_all_summaries(TYPING_DATA_ROOT)
    if df_typing is not None and not df_typing.empty:
        plot_typing(df_typing, output_dir)
        print("Generated Typing plots.")
    else:
        print("No Typing data found.")

    # Gesture
    df_gesture = load_all_summaries(GESTURE_DATA_ROOT)
    if df_gesture is not None and not df_gesture.empty:
        plot_gesture(df_gesture, output_dir)
        print("Generated Gesture plots.")
    else:
        print("No Gesture data found.")

if __name__ == "__main__":
    main()