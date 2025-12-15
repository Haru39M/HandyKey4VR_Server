import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os

def load_and_process_logs(log_dir="logs"):
    # summaryログのみを対象にする
    files = glob.glob(os.path.join(log_dir, "*_summary.csv"))
    
    if not files:
        print("No summary log files found.")
        return None

    df_list = []
    for f in files:
        try:
            temp_df = pd.read_csv(f)
            df_list.append(temp_df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not df_list:
        return None

    df = pd.concat(df_list, ignore_index=True)

    # --- WPMの再計算 (バグ修正用) ---
    # WPM = (文字数 / 5) / (秒数 / 60)
    df['WPM'] = (df['CharCount'] / 5) / (df['CompletionTime'] / 60)
    
    return df

def plot_results(df):
    if df is None or df.empty:
        return

    # スタイル設定
    sns.set_style("whitegrid")
    plt.figure(figsize=(12, 6))

    # 1. 学習曲線 (Trial IDごとのWPM推移)
    # Conditionごとに色分け
    sns.lineplot(
        data=df, 
        x="TrialID", 
        y="WPM", 
        hue="Condition", 
        style="Condition", 
        markers=True, 
        dashes=False,
        linewidth=2.5,
        markersize=8
    )

    plt.title("Learning Curve: WPM by Trial & Condition", fontsize=16)
    plt.xlabel("Trial ID (Sentence Count)", fontsize=12)
    plt.ylabel("WPM", fontsize=12)
    plt.ylim(0, df['WPM'].max() + 10)
    plt.legend(title="Condition", fontsize=10, title_fontsize=12)
    
    # グラフを保存または表示
    output_path = "wpm_analysis.png"
    plt.savefig(output_path)
    print(f"Analysis chart saved to {output_path}")
    # plt.show() # ローカル環境ならコメントアウトを外す

    # 2. 統計量の表示
    print("\n--- Statistics (WPM) ---")
    stats = df.groupby("Condition")["WPM"].agg(['mean', 'std', 'min', 'max', 'count'])
    print(stats)

if __name__ == "__main__":
    print("Loading logs...")
    df = load_and_process_logs()
    
    if df is not None:
        print("Plotting results...")
        plot_results(df)
        
        # CSVとしても保存（分析用）
        df.to_csv("combined_analysis_data.csv", index=False)
        print("Combined data saved to combined_analysis_data.csv")
    else:
        print("No data to analyze.")