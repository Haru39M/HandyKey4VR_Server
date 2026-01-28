import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
import numpy as np
import pingouin as pg
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DATA_ROOT_BASE = "analyzed_data"
JST = timezone(timedelta(hours=+9), 'JST')

# 配色設定
PALETTE = {
    "Keyboard": "#333333",
    "Controller": "#007bff",
    "HandyKey4VR": "#35dc67",
    "Proposed": "#35dc67"
}

LABEL_MAP = {
    "Proposed": "HandyKey4VR",
    "Controller": "Controller",
    "Keyboard": "Keyboard"
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
    df["Condition"] = df["Condition"].map(LABEL_MAP).fillna(df["Condition"])
    
    numeric_cols = ['WPM', 'CER', 'KSPC', 'DurationSec', 'TrialID']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

def add_significance_labels(ax, df, dv, order):
    """
    RM-ANOVAと事後検定を行い、有意差があるペアにブラケットと*を表示する
    """
    # 被験者ごとの平均値を算出（統計検定用）
    df_stats = df.groupby(['ParticipantID', 'Condition'])[dv].mean().reset_index()
    
    if df_stats['Condition'].nunique() < 2:
        return

    try:
        # 反復測定一元配置分散分析
        aov = pg.rm_anova(data=df_stats, dv=dv, within='Condition', subject='ParticipantID')
        p_aov = aov['p-unc'][0]
        
        if p_aov < 0.05:
            # 事後検定 (Tukey/Holm)
            posthoc = pg.pairwise_tests(data=df_stats, dv=dv, within='Condition', 
                                        subject='ParticipantID', padjust='holm')
            
            # グラフ上の最大値を取得して描画高さを決める
            y_max = df[dv].max()
            y_range = y_max - df[dv].min()
            
            # 有意なペアを抽出して線を描画
            sig_pairs = posthoc[posthoc['p-corr'] < 0.05]
            
            for idx, row in sig_pairs.iterrows():
                idx1 = order.index(row['A'])
                idx2 = order.index(row['B'])
                p_val = row['p-corr']
                
                # アスタリスクの決定
                stars = "*" if p_val < 0.05 else ""
                if p_val < 0.01: stars = "**"
                if p_val < 0.001: stars = "***"
                
                # 線の高さを調整（重なり防止）
                h = y_max + (y_range * 0.05) * (idx + 1)
                
                ax.plot([idx1, idx1, idx2, idx2], [h, h + y_range*0.02, h + y_range*0.02, h], 
                        lw=1.5, color='black')
                ax.text((idx1 + idx2) * .5, h + y_range*0.02, stars, 
                        ha='center', va='bottom', color='black', fontweight='bold')
    except Exception as e:
        print(f"      Stats failed for {dv}: {e}")

def generate_typing_plots(df, output_dir, title_suffix=""):
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.size'] = 12
    order = ["Keyboard", "HandyKey4VR", "Controller"]

    # WPM Boxplot
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="WPM", palette=PALETTE, hue="Condition", 
                order=order, legend=False, ax=ax)
    # sns.stripplot(data=df, x="Condition", y="WPM", color=".3", alpha=0.3, order=order, ax=ax)
    add_significance_labels(ax, df, "WPM", order)
    plt.title(f"Typing Speed (WPM) {title_suffix}")
    save_plot("typing_wpm_boxplot", output_dir)

    # WPM Learning Curve
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="TrialID", y="WPM", hue="Condition", palette=PALETTE, 
                 hue_order=order, marker="o", errorbar='sd')
    plt.title(f"Typing Learning Curve {title_suffix}")
    plt.grid(True, linestyle='--', alpha=0.5)
    save_plot("typing_wpm_learning_curve", output_dir)

    # CER Boxplot
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="CER", palette=PALETTE, hue="Condition", 
                order=order, legend=False, ax=ax)
    add_significance_labels(ax, df, "CER", order)
    plt.title(f"Character Error Rate (CER) {title_suffix}")
    save_plot("typing_cer_boxplot", output_dir)

    # KSPC Boxplot
    if 'KSPC' in df.columns:
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.boxplot(data=df, x="Condition", y="KSPC", palette=PALETTE, hue="Condition", 
                    order=order, legend=False, ax=ax)
        plt.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='Ideal (1.0)')
        add_significance_labels(ax, df, "KSPC", order)
        plt.title(f"Keystrokes Per Character (KSPC) {title_suffix}")
        plt.legend()
        save_plot("typing_kspc_boxplot", output_dir)

def main():
    base_output_dir = get_base_output_dir()
    print(f"Results will be saved to: {base_output_dir}")

    if not os.path.exists(DATA_ROOT_BASE):
        print(f"Directory {DATA_ROOT_BASE} not found.")
        return

    subdirs = [d for d in os.listdir(DATA_ROOT_BASE) if os.path.isdir(os.path.join(DATA_ROOT_BASE, d))]
    target_subdirs = [d for d in subdirs if "typing" in d]

    for subdir in target_subdirs:
        print(f"\nProcessing directory: {subdir}")
        full_path = os.path.join(DATA_ROOT_BASE, subdir)
        df = load_summaries(full_path)
        
        if df is None or df.empty:
            continue
        
        out_dir = os.path.join(base_output_dir, subdir)
        suffix = "(Practice)" if "practice" in subdir else ""
        generate_typing_plots(df, out_dir, suffix)

if __name__ == "__main__":
    main()