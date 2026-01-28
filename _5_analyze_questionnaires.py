import pandas as pd
import numpy as np
import os
import glob
import pingouin as pg
from scipy import stats as sp_stats
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta, timezone

# --- 設定 ---
INPUT_DIR = "logs/logs_questionnaire"
OUTPUT_BASE = "analysis_results"
JST = timezone(timedelta(hours=+9), 'JST')

# pandasの将来的な警告への対応
pd.set_option('future.no_silent_downcasting', True)

# ラベルのマッピング定義
CONDITION_MAP = {
    "キーボード": "Keyboard",
    "Keyboard": "Keyboard",
    "コントローラー": "VR Controller",
    "Controller": "VR Controller",
    "提案デバイス": "HandyKey4VR",
    "Proposed": "HandyKey4VR"
}

# 統一した配色設定（マッピング後の名前をキーにする）
PALETTE = {
    "Keyboard": "#333333",
    "VR Controller": "#007bff",
    "HandyKey4VR": "#35dc67"
}

# リッカート尺度のマッピング
LIKERT_MAP = {
    "とてもそう思う": 5,
    "ややそう思う": 4,
    "どちらとも言えない": 3,
    "あまりそう思わない": 2,
    "まったくそう思わない": 1
}

def get_output_dir():
    """実行時刻に基づいた出力ディレクトリを作成して返す"""
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_BASE, timestamp, "questionnaire")
    os.makedirs(path, exist_ok=True)
    return path

def save_plot(filename, output_dir):
    """グラフを3つの形式で保存する"""
    base_path = os.path.join(output_dir, filename)
    plt.savefig(base_path + ".png", dpi=300, bbox_inches='tight')
    plt.savefig(base_path + ".svg", format='svg', bbox_inches='tight')
    plt.savefig(base_path + ".pdf", format='pdf', bbox_inches='tight')
    print(f"    Saved plot: {filename}")
    plt.close()

def preprocess_data(df):
    """日本語回答の数値化と、条件名の英語化を行う"""
    # 数値化
    df = df.replace(LIKERT_MAP).infer_objects(copy=False)
    # 条件名の英語化
    if '条件' in df.columns:
        df['Condition'] = df['条件'].map(CONDITION_MAP)
    elif 'Condition' in df.columns:
        df['Condition'] = df['Condition'].map(CONDITION_MAP)
    return df

# --- SUS計算ロジック ---

def calculate_sus_score(row):
    """
    SUSスコア計算:
    奇数項目(1,3,5,7,9): 回答値 - 1
    偶数項目(2,4,6,8,10): 5 - 回答値
    合計を2.5倍する
    """
    q_cols = [c for c in row.index if "質問項目" in c]
    if len(q_cols) != 10:
        return np.nan
    
    score = 0
    for i, col in enumerate(q_cols):
        val = row[col]
        if (i + 1) % 2 != 0: # 奇数
            score += (val - 1)
        else: # 偶数
            score += (5 - val)
    return score * 2.5

# --- 可視化モジュール ---

def plot_sus(df_sub, output_dir):
    """SUSスコアの箱ひげ図を作成"""
    plt.figure(figsize=(8, 6))
    # SUSは全条件でプロット
    order = ["Keyboard", "VR Controller", "HandyKey4VR"]
    # 存在する条件のみに絞る
    present_order = [o for o in order if o in df_sub['Condition'].unique()]
    
    sns.boxplot(data=df_sub, x='Condition', y='SUS_Score', palette=PALETTE, order=present_order)
    sns.stripplot(data=df_sub, x='Condition', y='SUS_Score', color=".3", alpha=0.5, order=present_order)
    plt.title("System Usability Scale (SUS) Score")
    plt.ylabel("SUS Score (0-100)")
    plt.ylim(0, 105)
    save_plot("sus_boxplot", output_dir)

def plot_nasa_tlx(df_tlx, output_dir):
    """NASA-TLXの指標別棒グラフを作成（タスク別）"""
    metrics = ['Mental', 'Physical', 'Temporal', 'Performance', 'Effort', 'Frustration']
    
    # Conditionを英語化
    df_tlx['Condition'] = df_tlx['Condition'].map(CONDITION_MAP)
    
    for task in df_tlx['Task'].unique():
        df_task = df_tlx[df_tlx['Task'] == task].copy()
        
        # タスクに応じて表示する条件（凡例）を制限
        if task == 'gesture':
            hue_order = ["VR Controller", "HandyKey4VR"]
        else:
            hue_order = ["Keyboard", "VR Controller", "HandyKey4VR"]
        
        # 存在する条件のみにフィルタ
        df_task = df_task[df_task['Condition'].isin(hue_order)]
        
        df_melt = df_task.melt(id_vars=['Condition'], value_vars=metrics, 
                               var_name='Metric', value_name='Score')
        
        plt.figure(figsize=(10, 6))
        sns.barplot(data=df_melt, x='Metric', y='Score', hue='Condition', palette=PALETTE, 
                    hue_order=hue_order, capsize=.1)
        plt.title(f"NASA-TLX Workload Profiles [{task.capitalize()}]")
        plt.ylabel("Score (0-100)")
        plt.ylim(0, 100)
        plt.legend(title="Method", loc='upper right')
        save_plot(f"nasa_tlx_{task}_profile", output_dir)

def plot_likert_items(df_num, title_prefix, output_dir):
    """質問項目ごとの平均値棒グラフを作成"""
    q_cols = [c for c in df_num.columns if "質問項目" in c]
    rename_map = {col: f"Q{i+1}" for i, col in enumerate(q_cols)}
    df_plot = df_num.rename(columns=rename_map)
    
    # タスクに応じて表示する条件を制限
    if "Gesture" in title_prefix:
        hue_order = ["VR Controller", "HandyKey4VR"]
    else:
        hue_order = ["Keyboard", "VR Controller", "HandyKey4VR"]
        
    # 存在する条件のみにフィルタ
    df_plot = df_plot[df_plot['Condition'].isin(hue_order)]
    
    df_melt = df_plot.melt(id_vars=['Condition'], value_vars=list(rename_map.values()), 
                           var_name='Question', value_name='Score')
    
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_melt, x='Question', y='Score', hue='Condition', palette=PALETTE, 
                hue_order=hue_order, capsize=.05)
    plt.title(f"Questionnaire Ratings: {title_prefix}")
    plt.ylabel("Rating (1-5)")
    plt.ylim(1, 5.5)
    plt.axhline(y=3, color='gray', linestyle='--', alpha=0.5)
    plt.legend(title="Method", loc='upper right')
    save_plot(f"{title_prefix.lower().replace(' ', '_')}_items_bar", output_dir)

# --- 分析実行モジュール ---

def analyze_sus(df, output_path, output_dir):
    """SUSのスコア計算と検定・可視化"""
    df_num = preprocess_data(df)
    df_num['SUS_Score'] = df_num.apply(calculate_sus_score, axis=1)
    
    id_col = "ID(イニシャル＋誕生月、例→HarutoWakayama→HW04)"
    df_sub = df_num.groupby([id_col, 'Condition'])['SUS_Score'].mean().reset_index()
    
    with open(output_path, 'a', encoding='utf-8') as f:
        f.write("\n=== System Usability Scale (SUS) Analysis ===\n")
        summary = df_sub.groupby('Condition')['SUS_Score'].agg(['mean', 'std', 'count']).reset_index()
        f.write(summary.to_string(index=False) + "\n")
        
        compare_df = df_sub[df_sub['Condition'].isin(['HandyKey4VR', 'VR Controller'])]
        if compare_df['Condition'].nunique() == 2:
            f.write("\n[Wilcoxon Signed-Rank Test (HandyKey4VR vs VR Controller)]\n")
            x = compare_df[compare_df['Condition'] == 'HandyKey4VR']['SUS_Score']
            y = compare_df[compare_df['Condition'] == 'VR Controller']['SUS_Score']
            if len(x) == len(y):
                res = pg.wilcoxon(x, y)
                f.write(res.to_string() + "\n")
    
    plot_sus(df_sub, output_dir)

def analyze_likert_items(df, title, output_path, output_dir):
    """Q1〜Qnの各項目に対する統計解析・可視化"""
    df_num = preprocess_data(df)
    q_cols = [c for c in df_num.columns if "質問項目" in c]
    id_col = "ID(イニシャル＋誕生月、例→HarutoWakayama→HW04)"
    
    with open(output_path, 'a', encoding='utf-8') as f:
        f.write(f"\n=== {title} Item-by-Item Analysis ===\n")
        for q in q_cols:
            df_item = df_num.groupby([id_col, 'Condition'])[q].mean().reset_index()
            stats = df_item.groupby('Condition')[q].agg(['mean', 'std']).reset_index()
            f.write(f"\n--- {q} ---\n" + stats.to_string(index=False) + "\n")
            
            try:
                pivoted = df_item.pivot(index=id_col, columns='Condition', values=q).dropna()
                if df_item['Condition'].nunique() == 3 and len(pivoted) >= 3:
                    res_f = sp_stats.friedmanchisquare(*[pivoted[c] for c in pivoted.columns])
                    f.write(f"[Friedman] p={res_f.pvalue:.4f}\n")
                    if res_f.pvalue < 0.05:
                        posthoc = pg.pairwise_tests(data=df_item, dv=q, within='Condition', subject=id_col, parametric=False, padjust='holm')
                        f.write(posthoc.to_string() + "\n")
                elif df_item['Condition'].nunique() == 2:
                    conds = df_item['Condition'].unique()
                    res = pg.wilcoxon(df_item[df_item['Condition']==conds[0]][q], df_item[df_item['Condition']==conds[1]][q])
                    f.write(f"[Wilcoxon] p={res['p-val'].values[0]:.4f}\n")
            except Exception as e:
                f.write(f"Test error: {e}\n")

    plot_likert_items(df_num, title, output_dir)

# --- メイン処理 ---

def main():
    out_dir = get_output_dir()
    print(f"Starting Questionnaire Analysis. Results in: {out_dir}")

    # 1. SUS
    sus_file = os.path.join(INPUT_DIR, "SystemUsabilityScale_ans_forAnalyze.csv")
    if os.path.exists(sus_file):
        analyze_sus(pd.read_csv(sus_file), os.path.join(out_dir, "sus_report.txt"), out_dir)

    # 2. Gesture
    gesture_file = os.path.join(INPUT_DIR, "GestureTest_ans_forAnalyze.csv")
    if os.path.exists(gesture_file):
        analyze_likert_items(pd.read_csv(gesture_file), "Gesture Test", os.path.join(out_dir, "gesture_items_report.txt"), out_dir)

    # 3. Typing
    typing_file = os.path.join(INPUT_DIR, "TypingTest_ans_forAnalyze.csv")
    if os.path.exists(typing_file):
        analyze_likert_items(pd.read_csv(typing_file), "Typing Test", os.path.join(out_dir, "typing_items_report.txt"), out_dir)

    # 4. NASA-TLX Visualization
    try:
        import importlib
        stat_module = importlib.import_module("4_stat_analysis")
        df_tlx = stat_module.load_nasa_tlx_data()
        if df_tlx is not None:
            plot_nasa_tlx(df_tlx, out_dir)
    except (ImportError, ModuleNotFoundError):
        print("Warning: 4_stat_analysis.py not found. Skipping NASA-TLX visualization.")

    print("\nAll analyses and visualizations finished.")

if __name__ == "__main__":
    main()