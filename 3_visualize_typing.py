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
    numeric_cols = ['ActiveWPM', 'CER', 'KSPC', 'DurationSec', 'TrialID']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

def generate_typing_plots(df, output_dir, title_suffix=""):
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.size'] = 12

    # WPM Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="WPM", palette=PALETTE, hue="Condition", legend=False)
    plt.title(f"WPM by Condition {title_suffix}")
    save_plot("typing_wpm_boxplot", output_dir)

    # WPM Learning Curve
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="TrialID", y="WPM", hue="Condition", palette=PALETTE, marker="o", errorbar='sd')
    plt.title(f"WPM Learning Curve {title_suffix}")
    plt.grid(True, linestyle='--', alpha=0.5)
    save_plot("typing_wpm_learning_curve", output_dir)

    # CER Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="CER", palette=PALETTE, hue="Condition", legend=False)
    plt.title(f"Character Error Rate (CER) {title_suffix}")
    plt.ylim(0, max(0.2, df['CER'].quantile(0.95)) if not df.empty else 0.5)
    save_plot("typing_cer_boxplot", output_dir)

    # KSPC Boxplot
    plt.figure(figsize=(8, 6))
    if 'KSPC' in df.columns:
        sns.boxplot(data=df, x="Condition", y="KSPC", palette=PALETTE, hue="Condition", legend=False)
        plt.title(f"Keystrokes Per Character (KSPC) {title_suffix}")
        plt.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='Ideal (1.0)')
        plt.legend()
        plt.ylim(0.8, max(1.5, df['KSPC'].quantile(0.95)) if not df.empty else 2.0)
        save_plot("typing_kspc_boxplot", output_dir)

def main():
    base_output_dir = get_base_output_dir()
    print(f"Results will be saved to: {base_output_dir}")

    # typing, typing_practice 両方を探す
    # analyzed_data 直下のディレクトリ名を取得
    if not os.path.exists(DATA_ROOT_BASE):
        print(f"Directory {DATA_ROOT_BASE} not found.")
        return

    subdirs = [d for d in os.listdir(DATA_ROOT_BASE) if os.path.isdir(os.path.join(DATA_ROOT_BASE, d))]
    target_subdirs = [d for d in subdirs if "typing" in d] # typing, typing_practice

    for subdir in target_subdirs:
        print(f"\nProcessing directory: {subdir}")
        full_path = os.path.join(DATA_ROOT_BASE, subdir)
        df = load_summaries(full_path)
        
        if df is None or df.empty:
            print(f"  No summary data found in {subdir}.")
            continue
        
        # 出力先: analysis_results/Timestamp/{subdir}
        out_dir = os.path.join(base_output_dir, subdir)
        
        # タイトルに (Practice) とつけるか判定
        suffix = "(Practice)" if "practice" in subdir else ""
        
        generate_typing_plots(df, out_dir, suffix)
        print(f"  -> Visualization complete for {subdir}")

if __name__ == "__main__":
    main()