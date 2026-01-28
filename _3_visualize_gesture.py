import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
import numpy as np
from scipy.stats import gaussian_kde
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DATA_ROOT_BASE = "analyzed_data"
JST = timezone(timedelta(hours=+9), 'JST')

# 配色設定
# HandyKey4VR: 緑, Controller: 青
PALETTE = {
    "Keyboard": "#333333",
    "Controller": "#007bff",
    "HandyKey4VR": "#35dc67",
    "Proposed": "#35dc67"
}

# 内部的な Condition 名を英語の正式名称に変換するためのマップ
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
    反応時間の確率密度関数 (Probability Density Function) を KDE を用いて描画し、
    平均値と最頻値（ピーク位置）を重ねて表示する。
    """
    plt.figure(figsize=(12, 7))
    
    # 1. データの加工: 内部名を正式名称に置換
    df_plot = df.copy()
    df_plot["Condition"] = df_plot["Condition"].map(LABEL_MAP).fillna(df_plot["Condition"])

    # 描画対象の条件を固定
    target_conditions = ["HandyKey4VR", "Controller"]
    df_filtered = df_plot[df_plot["Condition"].isin(target_conditions)]

    if df_filtered.empty:
        print("    Skipping distribution plot: No data for target conditions.")
        plt.close()
        return

    # 2. 近似曲線 (KDE) の描画
    ax = sns.kdeplot(data=df_filtered, x="ReactionTimeMs", hue="Condition", 
                palette=PALETTE, hue_order=target_conditions,
                fill=True, common_norm=False, alpha=0.2, linewidth=2.5,
                bw_adjust=1.5, gridsize=1000)

    # 3. 統計値（平均値・最頻値）の計算と描画
    # IndexErrorを避けるため、グラフオブジェクトではなくデータから直接計算
    for i, cond in enumerate(target_conditions):
        cond_data = df_filtered[df_filtered["Condition"] == cond]["ReactionTimeMs"].dropna()
        if len(cond_data) < 2: continue
        
        color = PALETTE.get(cond)
        
        # 平均値
        mean_val = cond_data.mean()
        
        # 最頻値（KDEピーク位置）を独自に計算
        # 描画されているKDEと同じバンド幅設定を使用してピークを探す
        kde = gaussian_kde(cond_data, bw_method='scott') # scottはbw_adjust=1相当のデフォルト
        # 探索範囲の設定
        x_range = np.linspace(cond_data.min(), cond_data.max(), 1000)
        y_kde = kde(x_range)
        mode_val = x_range[np.argmax(y_kde)]
        peak_y = np.max(y_kde)

        # 垂直線の描画
        ax.axvline(mean_val, color=color, linestyle='-', linewidth=1.5, alpha=0.8)
        ax.axvline(mode_val, color=color, linestyle='--', linewidth=1.5, alpha=0.8)

        # テキストラベルの配置
        text_y = peak_y * (0.8 - (i * 0.15))
        ax.text(mean_val + 50, text_y, f"{cond}\nMean: {mean_val:.0f}ms\nMode: {mode_val:.0f}ms", 
                color=color, fontweight='bold', fontsize=10, verticalalignment='top',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=2))

    # 学術的なタイトルと軸ラベル
    plt.title(f"Probability Density Function of Reaction Time estimated by KDE {title_suffix}", fontsize=13)
    plt.xlabel("Reaction Time (ms)", fontsize=12)
    plt.ylabel("Probability Density", fontsize=12)
    
    plt.xlim(0, df_filtered["ReactionTimeMs"].quantile(0.99))
    plt.ylim(bottom=0) 
    
    # 凡例の設定
    try:
        sns.move_legend(ax, "upper right", title="Condition")
    except:
        leg = ax.get_legend()
        if leg: leg.set_title("Condition")
    
    plt.grid(axis='x', linestyle='--', alpha=0.4)
    plt.tight_layout()
    save_plot("gesture_rt_distribution", output_dir)

def plot_gesture_results(df, output_dir, title_suffix=""):
    # 全てのグラフでラベルを統一
    df_plot = df.copy()
    df_plot["Condition"] = df_plot["Condition"].map(LABEL_MAP).fillna(df_plot["Condition"])
    target_order = ["HandyKey4VR", "Controller"]

    # 1. Boxplot (FutureWarning対策でhueを指定)
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=df_plot, x="Condition", y="ReactionTimeMs", hue="Condition", 
                palette=PALETTE, order=target_order, legend=False)
    plt.title(f"Gesture Reaction Time {title_suffix}")
    plt.ylabel("Time (ms)")
    save_plot("gesture_rt_boxplot", output_dir)
    
    # 2. Learning Curve
    plt.figure(figsize=(10, 5))
    sns.lineplot(data=df_plot, x="TrialID", y="ReactionTimeMs", hue="Condition", 
                 palette=PALETTE, hue_order=target_order, marker='o')
    plt.title(f"Gesture Learning Curve {title_suffix}")
    plt.ylabel("Mean Time (ms)")
    plt.xlabel("Trial ID")
    if not df_plot.empty:
        max_trial = int(df_plot["TrialID"].max())
        step = max(1, max_trial // 10)
        plt.xticks(range(1, max_trial + 1, step))
    save_plot("gesture_learning_curve", output_dir)
    
    # 3. By Type
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df_plot, x="TargetGesture", y="ReactionTimeMs", hue="Condition", 
                palette=PALETTE, hue_order=target_order)
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
        
        plot_gesture_results(df, output_dir, title_suffix)
        plot_gesture_distribution(df, output_dir, title_suffix)

if __name__ == "__main__":
    main()