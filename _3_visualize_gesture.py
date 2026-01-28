import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
import numpy as np
import pingouin as pg
from scipy.stats import gaussian_kde
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

# 内部的な名称を論文用の正式名称に変換
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
    if not df_list: return None
    
    df = pd.concat(df_list, ignore_index=True)
    # ラベルを統一
    df["Condition"] = df["Condition"].map(LABEL_MAP).fillna(df["Condition"])
    
    # 数値変換の強制
    if 'ReactionTimeMs' in df.columns:
        df['ReactionTimeMs'] = pd.to_numeric(df['ReactionTimeMs'], errors='coerce')
    if 'TrialID' in df.columns:
        df['TrialID'] = pd.to_numeric(df['TrialID'], errors='coerce')
    return df

def add_sig_paired(ax, df, dv, order):
    """
    2条件間の対応のあるt検定を行い、有意差がある場合にブラケットとアスタリスクを描画する
    """
    # 統計用データ作成 (被験者ごとの平均値)
    df_stats = df.groupby(['ParticipantID', 'Condition'])[dv].mean().reset_index()
    conds = [c for c in order if c in df_stats['Condition'].unique()]
    
    if len(conds) != 2:
        return

    try:
        x = df_stats[df_stats['Condition'] == conds[0]][dv]
        y = df_stats[df_stats['Condition'] == conds[1]][dv]
        
        # 対応のあるt検定
        res = pg.ttest(x, y, paired=True)
        p_val = res['p-val'].values[0]
        
        if p_val < 0.05:
            # アスタリスクの数
            stars = "*"
            if p_val < 0.01: stars = "**"
            if p_val < 0.001: stars = "***"
            
            # 描画位置の計算 (現在の表示範囲の上端付近)
            y_max = df[dv].quantile(0.95) # 外れ値を無視した最大値付近
            y_range = y_max * 0.1
            h = y_max + y_range * 0.5
            
            # ブラケットの描画 (位置0と1)
            ax.plot([0, 0, 1, 1], [h, h + y_range*0.2, h + y_range*0.2, h], lw=1.5, color='black')
            ax.text(0.5, h + y_range*0.2, stars, ha='center', va='bottom', color='black', fontweight='bold', fontsize=14)
            
            # ブラケットが収まるようにY軸を調整
            ax.set_ylim(0, h + y_range * 1.5)
    except Exception as e:
        print(f"      Significance labeling failed: {e}")

def plot_gesture_distribution(df, output_dir, title_suffix="", filename="gesture_rt_distribution", 
                             target_gesture=None, fixed_xlim=None, fixed_ylim=None):
    """
    反応時間の確率密度関数 (PDF) を描画し、統計値を重ねる
    """
    plt.figure(figsize=(12, 7))
    
    df_plot = df.copy()
    if target_gesture:
        df_plot = df_plot[df_plot["TargetGesture"] == target_gesture]
        title_header = f"[{target_gesture}] "
    else:
        title_header = "Overall "

    target_conditions = ["HandyKey4VR", "Controller"]
    df_filtered = df_plot[df_plot["Condition"].isin(target_conditions)]

    if df_filtered.empty or len(df_filtered) < 2:
        plt.close(); return

    # KDE描画
    ax = sns.kdeplot(data=df_filtered, x="ReactionTimeMs", hue="Condition", 
                palette=PALETTE, hue_order=target_conditions,
                fill=True, common_norm=False, alpha=0.2, linewidth=2.5,
                bw_adjust=1.5, gridsize=1000)

    # 統計値の計算
    stats_data = []
    current_max_density = 0
    for cond in target_conditions:
        cond_data = df_filtered[df_filtered["Condition"] == cond]["ReactionTimeMs"].dropna()
        if len(cond_data) < 2: continue
        
        mean_val = cond_data.mean()
        try:
            kde_func = gaussian_kde(cond_data, bw_method='scott')
            x_range = np.linspace(cond_data.min(), cond_data.max(), 1000)
            y_kde = kde_func(x_range)
            mode_val = x_range[np.argmax(y_kde)]
            current_max_density = max(current_max_density, np.max(y_kde))
            stats_data.append({"cond": cond, "mean": mean_val, "mode": mode_val})
        except: pass

    # 軸の設定
    xlim_max = fixed_xlim if fixed_xlim else df_filtered["ReactionTimeMs"].quantile(0.99)
    ylim_max = fixed_ylim if fixed_ylim else current_max_density * 1.6
    
    plt.xlim(0, xlim_max)
    plt.ylim(0, ylim_max)

    # 統計ラベルの描画
    for i, s in enumerate(stats_data):
        color = PALETTE.get(s["cond"])
        plt.axvline(s["mean"], color=color, linestyle='-', linewidth=1.5, alpha=0.7)
        plt.axvline(s["mode"], color=color, linestyle='--', linewidth=1.5, alpha=0.7)

        # テキスト位置
        text_y = ylim_max * (0.92 - i * 0.15)
        text_x = s["mean"] + (xlim_max * 0.02)
        ha = 'left'
        if text_x > xlim_max * 0.8:
            ha = 'right'
            text_x = s["mean"] - (xlim_max * 0.02)

        plt.text(text_x, text_y, f"{s['cond']}\nMean: {s['mean']:.0f}ms\nMode: {s['mode']:.0f}ms", 
                color=color, fontweight='bold', fontsize=10, 
                verticalalignment='center', horizontalalignment=ha,
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1))

    plt.title(f"Probability Density Function of Reaction Time (KDE) {title_suffix}", fontsize=13)
    plt.xlabel("Reaction Time (ms)", fontsize=12)
    plt.ylabel("Probability Density", fontsize=12)
    
    plt.xlim(0, df_filtered["ReactionTimeMs"].quantile(0.99))
    plt.ylim(bottom=0) 
    try:
        sns.move_legend(ax, "upper right", title="Condition")
    except:
        leg = ax.get_legend()
        if leg: leg.set_title("Condition")
    
    plt.grid(axis='x', linestyle='--', alpha=0.4)
    plt.tight_layout()
    save_plot(filename, output_dir)

def generate_gesture_plots(df, output_dir, title_suffix=""):
    order = ["HandyKey4VR", "Controller"]
    
    # 1. Boxplot (有意差ラベル付き)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.boxplot(data=df, x="Condition", y="ReactionTimeMs", hue="Condition", 
                palette=PALETTE, order=order, legend=False, ax=ax)
    # sns.stripplot(data=df, x="Condition", y="ReactionTimeMs", color=".3", alpha=0.3, order=order, ax=ax)
    
    # 有意差の図示
    add_sig_paired(ax, df, "ReactionTimeMs", order)
    
    plt.title(f"Gesture Reaction Time {title_suffix}")
    plt.ylabel("Time (ms)")
    save_plot("gesture_rt_boxplot", output_dir)

    # 2. Learning Curve
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="TrialID", y="ReactionTimeMs", hue="Condition", 
                 palette=PALETTE, hue_order=order, marker="o", errorbar='sd')
    plt.title(f"Gesture Learning Curve {title_suffix}")
    plt.ylabel("Mean Reaction Time (ms)")
    plt.xlabel("Trial ID")
    if not df.empty:
        max_trial = int(df["TrialID"].max())
        step = max(1, max_trial // 10)
        plt.xticks(range(1, max_trial + 1, step))
    save_plot("gesture_learning_curve", output_dir)
    
    # 3. By Type Boxplot
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df, x="TargetGesture", y="ReactionTimeMs", hue="Condition", 
                palette=PALETTE, hue_order=order)
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
        
        if df is None or df.empty: continue
        
        output_dir = os.path.join(base_output_dir, subdir)
        title_suffix = "(Practice)" if "practice" in subdir else ""

        # --- 共通スケールの計算 (配布図比較用) ---
        common_xlim = df["ReactionTimeMs"].quantile(0.99)
        common_ylim = 0
        for gesture in df["TargetGesture"].unique():
            for cond in ["HandyKey4VR", "Controller"]:
                data = df[(df["TargetGesture"]==gesture) & (df["Condition"]==cond)]["ReactionTimeMs"].dropna()
                if len(data) >= 2:
                    try:
                        kde = gaussian_kde(data)
                        common_ylim = max(common_ylim, np.max(kde(np.linspace(data.min(), data.max(), 200))))
                    except: pass
        common_ylim *= 1.6 # ラベル用の余白
        
        # 1. 箱ひげ図・学習曲線の生成
        generate_gesture_plots(df, output_dir, title_suffix)
        
        # 2. 全体分布図の生成
        plot_gesture_distribution(df, output_dir, title_suffix)
        
        # 3. ジェスチャ別分布図の生成 (共通スケール適用)
        gestures = sorted(df["TargetGesture"].unique())
        for gesture in gestures:
            filename = f"gesture_rt_dist_{gesture.lower().replace(' ', '_')}"
            plot_gesture_distribution(df, output_dir, title_suffix, filename, 
                                     target_gesture=gesture, 
                                     fixed_xlim=common_xlim, 
                                     fixed_ylim=common_ylim)

if __name__ == "__main__":
    main()