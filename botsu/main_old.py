import time
import random
from config import Config
from predictor import WordPredictor
from kat_display import KATDisplay   # 変更
from device_listener import DeviceListener # 変更
from evaluator import TaskEvaluator

class TypingSystem:
    def __init__(self):
        self.config = Config()
        
        # モデルロード
        self.predictor = WordPredictor(self.config.MODEL_PATH, self.config.WORDS_JSON)
        
        # KAT表示システム
        self.display = KATDisplay(
            self.config.VRCHAT_IP, 
            self.config.VRCHAT_PORT,
            self.config.KAT_SYNC_PARAM_COUNT,
            self.config.KAT_PARAM_VISIBLE,
            self.config.KAT_PARAM_POINTER,
            self.config.KAT_PARAM_CHAR_PREFIX
        )
        
        self.evaluator = TaskEvaluator(self.config.LOG_FILE)
        
        # 状態変数
        self.current_buffer = ""
        self.current_candidates = []
        self.selected_index = 0
        self.target_word = ""
        
        # デバイスリスナー (OSCサーバー) 起動
        self.listener = DeviceListener(
            ip=self.config.LISTEN_IP,
            port=self.config.LISTEN_PORT,
            on_digit=self.handle_digit,
            on_nav=self.handle_nav,
            on_confirm=self.handle_confirm,
            on_backspace=self.handle_backspace
        )
        self.listener.start()

    def start(self):
        print("System Started. Waiting for OSC input...")
        self.next_task()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")

    def next_task(self):
        self.target_word = random.choice(list(self.predictor.words_set))
        self.current_buffer = ""
        self.current_candidates = []
        self.selected_index = 0
        
        self.evaluator.start_task(self.target_word)
        self._refresh_display()

    def handle_digit(self, char):
        print(f"Input: {char}")
        self.current_buffer += char
        self.current_candidates = self.predictor.predict(self.current_buffer)
        self.selected_index = 0
        self._refresh_display()

    def handle_nav(self, direction):
        if not self.current_candidates:
            return
        
        new_idx = self.selected_index + direction
        if 0 <= new_idx < len(self.current_candidates):
            self.selected_index = new_idx
            self._refresh_display()

    def handle_confirm(self):
        if not self.current_candidates:
            return

        final_word = self.current_candidates[self.selected_index]
        print(f"Confirmed: {final_word}")
        
        # 評価
        success, wpm = self.evaluator.submit_answer(final_word)
        
        # 結果を一瞬表示するならここで sleep と display更新を入れる
        
        self.next_task()

    def handle_backspace(self):
        if len(self.current_buffer) > 0:
            self.current_buffer = self.current_buffer[:-1]
            if self.current_buffer:
                self.current_candidates = self.predictor.predict(self.current_buffer)
            else:
                self.current_candidates = []
            self.selected_index = 0
            self._refresh_display()

    def _refresh_display(self):
        self.display.update_view(
            self.target_word, 
            self.current_buffer, 
            self.current_candidates, 
            self.selected_index
        )

if __name__ == "__main__":
    system = TypingSystem()
    system.start()