import pandas as pd
import glob
import os
import pingouin as pg
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DATA_ROOT_BASE = "analyzed_data"
NASA_TLX_DIR = "logs/logs_nasa_tlx"
JST = timezone(timedelta(hours=+9), 'JST')

def get_output_dir():
    """実行時刻に基づいた出力ディレクトリを作成して返す"""
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    path = os.path.join("analysis_results", timestamp, "stats")
    os.makedirs(path, exist_ok=True)
    return path

# --- データ集約モジュール ---

def load_typing_data():
    """タイピングデータのサマリーを集約し、被験者ごとの平均値を算出して返す"""
    path_pattern = os.path.join(DATA_ROOT_BASE, "typing", "**", "*_summary.csv")
    files = glob.glob(path_pattern, recursive=True)
    if not files:
        print("Warning: No typing summary files found.")
        return None
    
    df = pd.concat([pd.read_csv(f) for f in files if os.path.getsize(f) > 0], ignore_index=True)
    return df.groupby(['ParticipantID', 'Condition']).mean(numeric_only=True).reset_index()

def load_gesture_data():
    """ジェスチャデータのサマリーを集約して返す"""
    path_pattern = os.path.join(DATA_ROOT_BASE, "gesture", "**", "*_summary.csv")
    files = glob.glob(path_pattern, recursive=True)
    if not files:
        print("Warning: No gesture summary files found.")
        return None
    
    df = pd.concat([pd.read_csv(f) for f in files if os.path.getsize(f) > 0], ignore_index=True)
    return df.groupby(['ParticipantID', 'Condition']).mean(numeric_only=True).reset_index()

def load_nasa_tlx_data():
    """NASA-TLXの各CSVファイルを集約する"""
    files = glob.glob(os.path.join(NASA_TLX_DIR, "*.csv"))
    all_data = []
    
    # 認識対象の定義
    valid_tasks = ['typing', 'gesture']
    valid_conds = ['Proposed', 'Controller', 'Keyboard']

    for f in files:
        basename = os.path.basename(f).replace(".csv", "")
        parts = basename.split('_')
        
        # コンテンツベースの動的特定
        pid = parts[1]
        task = next((p for p in parts if p in valid_tasks), "unknown")
        cond = next((p for p in parts if p in valid_conds), "unknown")
        
        if task == "unknown" or cond == "unknown":
            continue
            
        try:
            df_temp = pd.read_csv(f)
            df_temp['ParticipantID'] = pid
            df_temp['Task'] = task
            df_temp['Condition'] = cond
            all_data.append(df_temp)
        except Exception as e:
            print(f"Error reading {f}: {e}")
    
    if not all_data: return None
    df_all = pd.concat(all_data, ignore_index=True)
    return df_all.groupby(['ParticipantID', 'Task', 'Condition']).mean(numeric_only=True).reset_index()

# --- 統計検定エンジン ---

def write_descriptive_stats(df, dv, f):
    """平均値と標準偏差を出力する（論文の表作成用）"""
    stats = df.groupby('Condition')[dv].agg(['mean', 'std', 'count']).reset_index()
    f.write("\n[Descriptive Statistics (Mean, SD)]\n")
    f.write(stats.to_string(index=False))
    f.write("\n")

def run_anova_pipeline(df, dv, report_file, title_prefix=""):
    """
    反復測定一元配置分散分析(RM-ANOVA)と事後検定を実行
    """
    with open(report_file, 'a', encoding='utf-8') as f:
        f.write(f"\n\n{'='*50}\n {title_prefix} Analysis for: {dv}\n{'='*50}\n")
        
        n_conds = df['Condition'].nunique()
        if n_conds < 2:
            f.write(f"Skipped: Only {n_conds} condition(s) found.\n")
            return

        # 記述統計の出力
        write_descriptive_stats(df, dv, f)

        try:
            # 1. ANOVA実行
            aov = pg.rm_anova(data=df, dv=dv, within='Condition', subject='ParticipantID', detailed=True)
            f.write("\n[1. RM-ANOVA Results]\n")
            f.write(aov.to_string())
            f.write("\n")

            p_val = aov['p-unc'][0]
            
            # 2. 事後検定 (Holm補正)
            if p_val < 0.05:
                f.write(f"\n[2. Post-hoc Tests (Significant p={p_val:.4f})]\n")
                posthoc = pg.pairwise_tests(data=df, dv=dv, within='Condition', 
                                            subject='ParticipantID', padjust='holm', effsize='hedges')
                f.write(posthoc.to_string())
            else:
                f.write(f"\n[2. Post-hoc Tests]\nNo significant main effect (p={p_val:.4f}).\n")
        
        except Exception as e:
            f.write(f"\n[Error during analysis]\n{str(e)}\n")

def run_paired_comparison(df, dv, report_file, title_prefix=""):
    """2条件間の対応のある比較（対応のあるt検定）を実行"""
    with open(report_file, 'a', encoding='utf-8') as f:
        f.write(f"\n\n{'='*50}\n {title_prefix} Paired Comparison for: {dv}\n{'='*50}\n")
        
        conds = sorted(df['Condition'].unique())
        if len(conds) != 2:
            f.write(f"Skipped paired comparison: Found {len(conds)} conditions.\n")
            return

        # 記述統計の出力
        write_descriptive_stats(df, dv, f)

        try:
            x = df[df['Condition'] == conds[0]][dv]
            y = df[df['Condition'] == conds[1]][dv]
            res = pg.ttest(x, y, paired=True)
            f.write(f"\n[T-test Result: {conds[0]} vs {conds[1]}]\n")
            f.write(res.to_string())
            f.write("\n")
        except Exception as e:
            f.write(f"\n[Error during t-test]\n{str(e)}\n")

# --- メインロジック ---

def main():
    out_dir = get_output_dir()
    print(f"Statistical analysis started. Results directory: {out_dir}")

    # 1. Typing Analysis
    df_typing = load_typing_data()
    if df_typing is not None:
        report = os.path.join(out_dir, "typing_stats_report.txt")
        for metric in ['WPM', 'CER', 'KSPC']:
            run_anova_pipeline(df_typing, metric, report, title_prefix="Typing Task")
        print(f"  - Typing stats completed: {os.path.basename(report)}")

    # 2. Gesture Analysis
    df_gesture = load_gesture_data()
    if df_gesture is not None:
        report = os.path.join(out_dir, "gesture_stats_report.txt")
        run_paired_comparison(df_gesture, 'ReactionTimeMs', report, title_prefix="Gesture Task")
        print(f"  - Gesture stats completed: {os.path.basename(report)}")

    # 3. NASA-TLX Analysis
    df_tlx = load_nasa_tlx_data()
    if df_tlx is not None:
        report = os.path.join(out_dir, "nasa_tlx_stats_report.txt")
        tlx_metrics = ['Mental', 'Physical', 'Temporal', 'Performance', 'Effort', 'Frustration']
        
        for task in sorted(df_tlx['Task'].unique()):
            df_task_specific = df_tlx[df_tlx['Task'] == task]
            for m in tlx_metrics:
                run_anova_pipeline(df_task_specific, m, report, title_prefix=f"NASA-TLX [{task}]")
        
        print(f"  - NASA-TLX stats completed: {os.path.basename(report)}")

    print("\nAll statistical analyses finished successfully.")

if __name__ == "__main__":
    main()