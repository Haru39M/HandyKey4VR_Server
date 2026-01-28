import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
import numpy as np
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DATA_ROOT_BASE = "analyzed_data"
JST = timezone(timedelta(hours=+9), 'JST')

# 配色とラベルのマッピング
# 論文用に "Proposed" を "HandyKey4VR" に置き換えます
PALETTE = {
    "Keyboard": "#333333",
    "Controller": "#007bff",
    "HandyKey4VR": "#35dc67"
}

# 内部的な Condition 名を変換するためのマップ
LABEL_MAP = {
    "Proposed": "HandyKey4VR",
    "Controller": "Controller"
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
    return pd.concat(df_list, ignore_index=True) if df_list else None

def plot_gesture_distribution(df, output_dir, title_suffix=""):
    """
    反応時間の確率密度関数 (Probability Density Function) を KDE を用いて描画する。
    """
    plt.figure(figsize=(10, 6))
    
    # ラベルを HandyKey4VR に変換
    df_plot = df.copy()
    df_plot["Condition"] = df_plot["Condition"].map(LABEL_MAP).fillna(df_plot["Condition"])

    # 描画対象の条件（Controller, HandyKey4VR）
    target_conditions = ["HandyKey4VR", "Controller"]
    df_filtered = df_plot[df_plot["Condition"].isin(target_conditions)]

    # 1. 近似曲線 (KDE: Kernel Density Estimation) の描画
    # bw_adjust=1.5 で平滑化を強め、gridsize=1000 で山の頂点を滑らかにします
    sns.kdeplot(data=df_filtered, x="ReactionTimeMs", hue="Condition", 
                palette=PALETTE, hue_order=target_conditions,
                fill=True, common_norm=False, alpha=0.2, linewidth=2.5,
                bw_adjust=1.5, gridsize=1000)

    # 学術的なタイトルと軸ラベル
    plt.title(f"Probability Density Function of Reaction Time estimated by KDE {title_suffix}", fontsize=13)
    plt.xlabel("Reaction Time (ms)", fontsize=12)
    plt.ylabel("Probability Density", fontsize=12)
    
    # 軸の調整
    plt.xlim(0, df_filtered["ReactionTimeMs"].quantile(0.99)) # 上位1%を除外して表示を見やすく
    plt.ylim(bottom=0) # 下限値を0に固定
    
    # 凡例の設定（右上に配置）
    plt.legend(title="Condition", labels=["Controller", "HandyKey4VR"], 
               title_fontsize='12', fontsize='11', loc='upper right')
    
    plt.grid(axis='x', linestyle='--', alpha=0.4)
    plt.tight_layout()
    save_plot("gesture_rt_distribution", output_dir)

def plot_gesture_results(df, output_dir, title_suffix=""):
    # ラベル変換
    df_plot = df.copy()
    df_plot["Condition"] = df_plot["Condition"].map(LABEL_MAP).fillna(df_plot["Condition"])

    # Boxplot
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df_plot, x="Condition", y="ReactionTimeMs", palette=PALETTE, order=["HandyKey4VR","Controller"])
    # sns.stripplot(data=df_plot, x="Condition", y="ReactionTimeMs", color=".3", alpha=0.5, order=["HandyKey4VR", "Controller"])
    plt.title(f"Gesture Reaction Time {title_suffix}")
    plt.ylabel("Time (ms)")
    save_plot("gesture_rt_boxplot", output_dir)
    
    # Learning Curve
    plt.figure(figsize=(10, 5))
    sns.lineplot(data=df_plot, x="TrialID", y="ReactionTimeMs", hue="Condition", palette=PALETTE, marker='o')
    plt.title(f"Gesture Learning Curve {title_suffix}")
    plt.ylabel("Mean Time (ms)")
    plt.xlabel("Trial ID")
    if not df.empty:
        max_trial = int(df["TrialID"].max())
        step = max(1, max_trial // 10)
        plt.xticks(range(1, max_trial + 1, step))
    save_plot("gesture_learning_curve", output_dir)
    
    # By Type
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df_plot, x="TargetGesture", y="ReactionTimeMs", hue="Condition", palette=PALETTE)
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

    subdirs = [d for d in os.listdir(DATA_ROOT_BASE) if os.path.isdir(os.path.join(DATA_ROOT_BASE, d))]
    target_subdirs = [d for d in subdirs if "gesture" in d]

    for subdir in target_subdirs:
        print(f"\nProcessing directory: {subdir}")
        full_path = os.path.join(DATA_ROOT_BASE, subdir)
        df = load_summaries(full_path)
        
        if df is None or df.empty:
            print(f"  No summary data found in {subdir}.")
            continue
        
        output_dir = os.path.join(base_output_dir, subdir)
        title_suffix = "(Practice)" if "practice" in subdir else ""
        
        # 各種グラフの生成
        plot_gesture_results(df, output_dir, title_suffix)
        plot_gesture_distribution(df, output_dir, title_suffix)

if __name__ == "__main__":
    main()