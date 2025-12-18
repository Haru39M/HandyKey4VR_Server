import sys
import os
import time
import threading

# --- 1. パス設定 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
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

# --- 3. アプリケーションクラス ---
class TypingSystem:
    def __init__(self, osc_port=8000):
        # 設定
        self.osc_port = osc_port
        self.model_path = os.path.join(parent_dir, 'wiki_en_token.arpa.bin')
        
        # ★設定: VRChatへの送信間隔（秒）
        # 0.2秒 = 1秒間に5回更新。これ以上速いとVRChatが詰まることが多いです。
        self.send_interval = 0.5
        self.last_send_time = 0
        
        # モジュール初期化
        print("システムを初期化中...")
        self.predictor = WordPredictor(self.model_path)
        self.display = VRChatTypingDisplay(port=3000)
        
        # 状態変数
        self.teacher_text = "ReferenceText"
        self.candidates = []
        self.selected_index = 0
        self.is_dirty = True

    # === OSCハンドラ ===

    def on_input_char(self, address, *args):
        if not args: return
        val = int(args[0])
        print(f"[OSC] Char Input: {val}")
        
        self.predictor.handle_index_input(val)
        self.selected_index = 0
        self.is_dirty = True

    def on_input_nav(self, address, *args):
        if not args: return
        direction = int(args[0])
        print(f"[OSC] Nav Input: {direction}")
        
        new_index = self.selected_index + direction
        if new_index < 0: new_index = 5
        if new_index > 5: new_index = 0
        
        self.selected_index = new_index
        self.is_dirty = True

    def on_input_backspace(self, address, *args):
        print("[OSC] Backspace Input")
        self.predictor.handle_backspace()
        self.selected_index = 0
        self.is_dirty = True

    def on_input_confirm(self, address, *args):
        print("[OSC] Confirm Input")
        if 0 <= self.selected_index < len(self.candidates):
            chosen_word = self.candidates[self.selected_index]
            print(f"★ 決定された単語: {chosen_word}")
        
        self.predictor.clear()
        self.candidates = []
        self.selected_index = 0
        self.is_dirty = True
        
        # 決定時は即座に反映させたいので、タイマーをリセットして強制更新させる手もある
        self.last_send_time = 0 

    # === メイン処理 ===
    
    def update_candidates(self):
        """予測モジュールから候補を取得"""
        if self.predictor.get_current_sequence():
            self.candidates = self.predictor.predict_top_words(limit=6)
        else:
            self.candidates = []

    def start(self):
        # 1. OSCサーバーの設定
        disp = dispatcher.Dispatcher()
        disp.map("/input/char", self.on_input_char)
        disp.map("/input/nav", self.on_input_nav)
        disp.map("/input/backspace", self.on_input_backspace)
        disp.map("/input/confirm", self.on_input_confirm)

        server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", self.osc_port), disp)
        
        # 2. OSCサーバーを別スレッドで開始
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        print(f"\n=== System Running ===")
        print(f"OSC Server listening on port: {self.osc_port}")
        print(f"VRChat Update Interval: {self.send_interval}s")
        print("Press Ctrl+C to exit.\n")

        # 3. メインループ (画面更新監視)
        try:
            while True:
                # 計算負荷を下げるための微小ウェイト (OSC受信スレッドには影響しない)
                time.sleep(0.01)

                if self.is_dirty:
                    # 1. 内部データ(候補)は常に最新にする
                    self.update_candidates()
                    
                    # 2. 画面更新(HTTP送信)は一定間隔に制限する
                    current_time = time.time()
                    if current_time - self.last_send_time > self.send_interval:
                        
                        try:
                            self.display.update_display(
                                teacher_text=self.teacher_text,
                                candidates=self.candidates,
                                selected_index=self.selected_index
                            )
                            # 送信成功時刻を更新
                            self.last_send_time = current_time
                            
                            # 画面とデータが一致したのでフラグを下ろす
                            self.is_dirty = False
                            
                        except Exception as e:
                            print(f"[Error] Display update failed: {e}")

        except KeyboardInterrupt:
            print("\nShutting down...")
            server.shutdown()

if __name__ == "__main__":
    app = TypingSystem(osc_port=8000)
    app.start()