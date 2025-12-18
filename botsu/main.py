import time
import os
import sys
# --- 【追加】親ディレクトリ(ルート)をモジュール検索パスに追加 ---
current_dir = os.path.dirname(os.path.abspath(__file__)) # systemフォルダのパス
parent_dir = os.path.dirname(current_dir)                # その上のルートフォルダのパス
sys.path.append(parent_dir)
# -----------------------------------------------------------
# 作成したモジュール
from vrc_typing_display import VRChatTypingDisplay
from word_predictor import WordPredictor

def main():
    # 1. 各モジュールの初期化
    try:
        # 表示用モジュール (WSLの場合はIP自動解決)
        display = VRChatTypingDisplay(port=3000)
        # ルートディレクトリのパスを使って、モデルファイルの絶対パスを作成
        model_path = os.path.join(parent_dir, 'wiki_en_token.arpa.bin')
        # 予測用モジュール (モデル読み込み)
        # predictor = WordPredictor(model_path='wiki_en_token.arpa.bin')
        # パスを指定して初期化
        predictor = WordPredictor(model_path=model_path)
        
    except Exception as e:
        print(f"Initialization Error: {e}")
        return

    # 2. 変数定義
    teacher_text = "Hello World" # 教師テキスト
    candidates = []              # 現在の予測候補
    selected_index = 0           # 選択中の候補インデックス (0-5)

    print("System Started. Press Ctrl+C to exit.")

    # --- メインループ (疑似コード) ---
    # 実際にはここで python-osc の Dispatcher 等を動かすことになります
    
    while True:
        try:
            # === 入力シミュレーション (実際はOSC受信イベントで行う処理) ===
            # 例: デバイスから '0' (t/g/b...) が送られてきたと仮定
            # input_val = receive_osc_input() 
            
            # if input_type == "/input/char":
            #     predictor.handle_index_input(input_val)
            #     selected_index = 0 # 文字入力したら選択位置はリセット
            
            # elif input_type == "/input/backspace":
            #     predictor.handle_backspace()
            
            # elif input_type == "/input/nav":
            #     selected_index += input_val # +1 or -1
            
            # elif input_type == "/input/confirm":
            #     # 決定処理 (教師テキストの判定など)
            #     predictor.clear()
            #     candidates = []
            
            # === 予測の実行 ===
            # 現在の入力バッファに基づいて候補を更新
            candidates = predictor.predict_top_words(limit=6)
            
            # === VRChatへの表示更新 ===
            display.update_display(
                teacher_text=teacher_text,
                candidates=candidates,
                selected_index=selected_index
            )
            
            time.sleep(0.1) # ループ待機

        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()