import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DATA_ROOT = "analyzed_data/gesture"
JST = timezone(timedelta(hours=+9), 'JST')

PALETTE = {
    "Keyboard": "#333333",
    "Controller": "#007bff",
    "Proposed": "#35dc67"
}

def get_output_dir():
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("analysis_results", timestamp, "gesture")
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
    
    # 数値型変換
    if 'ReactionTimeMs' in df.columns:
        df['ReactionTimeMs'] = pd.to_numeric(df['ReactionTimeMs'], errors='coerce')
    if 'TrialID' in df.columns:
        df['TrialID'] = pd.to_numeric(df['TrialID'], errors='coerce')
        
    return df

def main():
    output_dir = get_output_dir()
    print(f"Gesture graphs will be saved to: {output_dir}")

    df = load_all_summaries(DATA_ROOT)
    if df is None or df.empty:
        print("No gesture summary data found.")
        return

    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.size'] = 12

    # 1. Reaction Time Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="ReactionTimeMs", palette=PALETTE, hue="Condition", legend=False)
    plt.title("Gesture Reaction Time")
    plt.ylabel("Time (ms)")
    save_plot("gesture_rt_boxplot", output_dir)

    # 2. Learning Curve
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="TrialID", y="ReactionTimeMs", hue="Condition", palette=PALETTE, marker="o", errorbar='sd')
    plt.title("Gesture Reaction Time Learning Curve")
    plt.ylabel("Time (ms)")
    plt.xlabel("Trial ID")
    plt.grid(True, linestyle='--', alpha=0.5)
    
    if not df.empty:
        max_trial = int(df["TrialID"].max())
        step = max(1, max_trial // 10)
        plt.xticks(range(1, max_trial + 1, step))
        
    save_plot("gesture_learning_curve", output_dir)
    
    # 3. By Gesture Type
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df, x="TargetGesture", y="ReactionTimeMs", hue="Condition", palette=PALETTE)
    plt.title("Reaction Time by Gesture Type")
    plt.xticks(rotation=45)
    plt.ylabel("Time (ms)")
    plt.tight_layout()
    save_plot("gesture_rt_by_type", output_dir)

    print("Gesture visualization complete.")

if __name__ == "__main__":
    main()