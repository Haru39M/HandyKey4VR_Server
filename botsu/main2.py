import sys
import os
import time
import threading

# --- 1. パス設定 (親ディレクトリのモジュールを読み込むため) ---
current_dir = os.path.dirname(os.path.abspath(__file__)) # systemフォルダ
parent_dir = os.path.dirname(current_dir)                # ルートフォルダ
sys.path.append(parent_dir)

# --- 2. 外部ライブラリ & モジュールのインポート ---
from pythonosc import dispatcher
from pythonosc import osc_server

try:
    from word_predictor import WordPredictor
    from vrc_typing_display import VRChatTypingDisplay
except ImportError as e:
    print("モジュールの読み込みに失敗しました。ディレクトリ構成を確認してください。")
    print(f"エラー詳細: {e}")
    sys.exit(1)

# --- 3. アプリケーションクラス (状態管理とロジック) ---
class TypingSystem:
    def __init__(self, osc_port=8000):
        # 設定
        self.osc_port = osc_port
        self.model_path = os.path.join(parent_dir, 'wiki_en_token.arpa.bin')
        
        # モジュール初期化
        print("システムを初期化中...")
        self.predictor = WordPredictor(self.model_path)
        self.display = VRChatTypingDisplay(port=3000) # Webツール側のポート
        
        # 状態変数
        self.teacher_text = "ReferenceText" # 例文
        self.candidates = []
        self.selected_index = 0
        self.is_dirty = True # 画面更新が必要かどうかのフラグ

    # === OSCハンドラ (TouchOSCからの入力を処理) ===

    def on_input_char(self, address, *args):
        """
        /input/char (int 0~7)
        文字入力受信
        """
        if not args: return
        val = int(args[0])
        print(f"[OSC] Char Input: {val}")
        
        self.predictor.handle_index_input(val)
        self.selected_index = 0 # 入力したら選択位置は先頭に戻す
        self.is_dirty = True    # 画面更新を要求

    def on_input_nav(self, address, *args):
        """
        /input/nav (int -1 or 1)
        候補選択カーソルの移動
        """
        if not args: return
        direction = int(args[0])
        print(f"[OSC] Nav Input: {direction}")
        
        # インデックスの加減算 (0 ~ 5 の範囲に収める)
        new_index = self.selected_index + direction
        if new_index < 0: new_index = 5
        if new_index > 5: new_index = 0
        
        self.selected_index = new_index
        self.is_dirty = True

    def on_input_backspace(self, address, *args):
        """
        /input/backspace
        一文字削除
        """
        print("[OSC] Backspace Input")
        self.predictor.handle_backspace()
        self.selected_index = 0
        self.is_dirty = True

    def on_input_confirm(self, address, *args):
        """
        /input/confirm
        決定操作
        """
        print("[OSC] Confirm Input")
        
        # 現在選択中の単語を取得
        if 0 <= self.selected_index < len(self.candidates):
            chosen_word = self.candidates[self.selected_index]
            print(f"★ 決定された単語: {chosen_word}")
            # ここで本来なら「確定済みテキスト」に追加する処理などを行う
        
        # 入力をクリアして次へ
        self.predictor.clear()
        self.candidates = []
        self.selected_index = 0
        self.is_dirty = True

    # === メイン処理 ===
    
    def update_candidates(self):
        """予測モジュールから候補を取得"""
        # 入力バッファがある時だけ予測する
        if self.predictor.get_current_sequence():
            self.candidates = self.predictor.predict_top_words(limit=6)
        else:
            self.candidates = []

    def start(self):
        # 1. OSCサーバーの設定
        disp = dispatcher.Dispatcher()
        # 画像の仕様に合わせてマッピング
        disp.map("/input/char", self.on_input_char)
        disp.map("/input/nav", self.on_input_nav)
        disp.map("/input/backspace", self.on_input_backspace)
        disp.map("/input/confirm", self.on_input_confirm)

        server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", self.osc_port), disp)
        
        # 2. OSCサーバーを別スレッドで開始
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True # メイン終了時に道連れにする
        server_thread.start()
        
        print(f"\n=== System Running ===")
        print(f"OSC Server listening on port: {self.osc_port}")
        print(f"Waiting for input from TouchOSC...")
        print("Press Ctrl+C to exit.\n")

        # 3. メインループ (画面更新監視)
        try:
            while True:
                if self.is_dirty:
                    # 候補データの更新
                    self.update_candidates()
                    
                    # 画面表示の更新 (HTTPリクエスト送信)
                    self.display.update_display(
                        teacher_text=self.teacher_text,
                        candidates=self.candidates,
                        selected_index=self.selected_index
                    )
                    
                    self.is_dirty = False # フラグを下ろす
                
                time.sleep(0.05) # CPU負荷を下げるための待機 (20fps程度)

        except KeyboardInterrupt:
            print("\nShutting down...")
            server.shutdown()

# --- 実行 ---
if __name__ == "__main__":
    # ポート番号はTouchOSCの設定に合わせて変更してください (デフォルト9000)
    app = TypingSystem(osc_port=8000)
    app.start()