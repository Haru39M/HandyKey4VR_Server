import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DATA_ROOT_BASE = "analyzed_data"
JST = timezone(timedelta(hours=+9), 'JST')

PALETTE = {
    "Keyboard": "#333333",
    "Controller": "#007bff",
    "Proposed": "#35dc67"
}

def get_base_output_dir():
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    return os.path.join("analysis_results", timestamp)

def save_plot(filename, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    base_path = os.path.join(output_dir, filename)
    plt.savefig(base_path + ".png", dpi=300, bbox_inches='tight')
    plt.savefig(base_path + ".svg", format='svg', bbox_inches='tight')
    plt.savefig(base_path + ".pdf", format='pdf', bbox_inches='tight')
    print(f"    Saved: {filename} -> {output_dir}")
    plt.close()

def load_summaries(target_dir):
    files = glob.glob(os.path.join(target_dir, "**", "*_summary.csv"), recursive=True)
    if not files: return None
    df_list = [pd.read_csv(f) for f in files if os.path.getsize(f) > 0]
    if not df_list: return None
    
    df = pd.concat(df_list, ignore_index=True)
    if 'ReactionTimeMs' in df.columns:
        df['ReactionTimeMs'] = pd.to_numeric(df['ReactionTimeMs'], errors='coerce')
    if 'TrialID' in df.columns:
        df['TrialID'] = pd.to_numeric(df['TrialID'], errors='coerce')
    return df

def generate_gesture_plots(df, output_dir, title_suffix=""):
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.size'] = 12

    # RT Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="ReactionTimeMs", palette=PALETTE, hue="Condition", legend=False)
    plt.title(f"Gesture Reaction Time {title_suffix}")
    plt.ylabel("Time (ms)")
    save_plot("gesture_rt_boxplot", output_dir)

    # Learning Curve
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="TrialID", y="ReactionTimeMs", hue="Condition", palette=PALETTE, marker="o", errorbar='sd')
    plt.title(f"Gesture Learning Curve {title_suffix}")
    plt.ylabel("Time (ms)")
    plt.xlabel("Trial ID")
    plt.grid(True, linestyle='--', alpha=0.5)
    
    if not df.empty:
        max_trial = int(df["TrialID"].max())
        step = max(1, max_trial // 10)
        plt.xticks(range(1, max_trial + 1, step))
    save_plot("gesture_learning_curve", output_dir)
    
    # By Type
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df, x="TargetGesture", y="ReactionTimeMs", hue="Condition", palette=PALETTE)
    plt.title(f"Reaction Time by Gesture Type {title_suffix}")
    plt.xticks(rotation=45)
    plt.ylabel("Time (ms)")
    plt.tight_layout()
    save_plot("gesture_rt_by_type", output_dir)

def main():
    base_output_dir = get_base_output_dir()
    print(f"Results will be saved to: {base_output_dir}")

    if not os.path.exists(DATA_ROOT_BASE):
        print(f"Directory {DATA_ROOT_BASE} not found.")
        return

    # gesture, gesture_practice を探す
    subdirs = [d for d in os.listdir(DATA_ROOT_BASE) if os.path.isdir(os.path.join(DATA_ROOT_BASE, d))]
    target_subdirs = [d for d in subdirs if "gesture" in d]

    for subdir in target_subdirs:
        print(f"\nProcessing directory: {subdir}")
        full_path = os.path.join(DATA_ROOT_BASE, subdir)
        df = load_summaries(full_path)
        
        if df is None or df.empty:
            print(f"  No summary data found in {subdir}.")
            continue
        
        out_dir = os.path.join(base_output_dir, subdir)
        suffix = "(Practice)" if "practice" in subdir else ""
        generate_gesture_plots(df, out_dir, suffix)
        print(f"  -> Visualization complete for {subdir}")

if __name__ == "__main__":
    main()