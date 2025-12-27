import json
import os
import time
import csv
import random
from datetime import datetime

class GestureTest:
    def __init__(self, gestures_path='gestures/gestures.json'):
        self.gestures_data = {}
        self.gesture_list = []
        self.current_gesture_id = None
        self.target_gesture = None
        
        # デバイスからの現在の入力状態
        # 初期状態は全てOPENとしておく
        self.current_device_state = {
            "T": "OPEN", "I": "OPEN", "M": "OPEN", "R": "OPEN", "P": "OPEN"
        }
        
        # テスト進行管理
        self.participant_id = "test"
        self.condition = "default"
        self.max_trials = 10
        self.completed_trials = 0
        self.is_running = False
        
        # 計測用
        self.trial_start_time = 0.0
        self.match_start_time = None # 一致し始めた時刻（チャタリング防止用）
        self.match_duration_threshold = 0.5 # 0.5秒間一致し続けたら完了とする
        
        # ログ用
        self.log_dir = "logs"
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # データ読み込み
        self.load_gestures(gestures_path)

    def load_gestures(self, path):
        if not os.path.exists(path):
            print(f"[GestureTest] Error: {path} not found.")
            return

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.gestures_data = data.get("Gestures", {})
            # IDのリストを作成 (例: ["0", "1", ...])
            self.gesture_list = list(self.gestures_data.keys())
            print(f"[GestureTest] Loaded {len(self.gesture_list)} gestures.")

    def configure_test(self, participant_id, condition, max_trials):
        self.participant_id = participant_id
        self.condition = condition
        self.max_trials = int(max_trials)
        self.completed_trials = 0
        self.is_running = True
        self.next_trial()

    def next_trial(self):
        """次のターゲットをランダムに設定"""
        if self.completed_trials >= self.max_trials:
            self.is_running = False
            self.target_gesture = None
            return

        # ランダムに選択
        self.current_gesture_id = random.choice(self.gesture_list)
        self.target_gesture = self.gestures_data[self.current_gesture_id]
        
        self.trial_start_time = time.time()
        self.match_start_time = None
        print(f"[GestureTest] Next Target: {self.target_gesture['GestureName']}")

    def update_input(self, input_state):
        """
        デバイスからの入力を更新する
        input_state: {"T": "CLOSE", "I": "OPEN", ...} のような辞書
        """
        # 部分的な更新も許容する
        for key, val in input_state.items():
            if key in self.current_device_state:
                self.current_device_state[key] = val
        
        # デバッグ: 入力更新時に内容を表示（必要に応じてコメントアウト）
        # print(f"[GestureInput] Updated: {input_state}")

    def check_state(self):
        """現在の状態を判定し、結果を返す（APIレスポンス用）"""
        if not self.is_running or not self.target_gesture:
            return {
                "is_running": False,
                "is_completed": True
            }

        # 1. 一致判定
        is_match = self._is_matching()
        
        # 2. 完了判定（一定時間一致が継続したか）
        is_trial_completed = False
        
        if is_match:
            if self.match_start_time is None:
                self.match_start_time = time.time()
            elif time.time() - self.match_start_time >= self.match_duration_threshold:
                # 完了！
                self._save_log()
                self.completed_trials += 1
                is_trial_completed = True
                # 次のトライアルへ（自動遷移）
                self.next_trial()
        else:
            self.match_start_time = None

        return {
            "is_running": self.is_running,
            "target": self.target_gesture,
            "current_input": self.current_device_state,
            "is_match": is_match,
            "progress": f"{self.completed_trials} / {self.max_trials}",
            "trial_completed_just_now": is_trial_completed
        }

    def _is_matching(self):
        """現在の入力がターゲットの定義を満たしているか"""
        if not self.target_gesture:
            return False

        target_state = self.target_gesture["State"]
        gesture_name = self.target_gesture.get("GestureName", "")
        
        # 1. 各指の状態が許可リストに含まれているかチェック
        for finger in ["T", "I", "M", "R", "P"]:
            current_val = self.current_device_state.get(finger, "UNKNOWN")
            allowed_vals = target_state.get(finger, [])
            
            # 定義されている状態リストに含まれていなければ不一致
            if current_val not in allowed_vals:
                # デバッグ用: 不一致の原因を表示（開発中のみ有効にすると便利）
                # print(f"[Mismatch] Finger: {finger}, Current: {current_val} (Type: {type(current_val)}), Allowed: {allowed_vals}")
                return False
        
        # 2. 特例判定: Neutralの場合、すべてが"OPEN"の状態（＝HandOpen）は除外する
        if gesture_name == "Neutral":
            all_open = True
            for finger in ["T", "I", "M", "R", "P"]:
                if self.current_device_state.get(finger) != "OPEN":
                    all_open = False
                    break
            
            # すべてOPENならNeutralとしては不一致とする
            if all_open:
                return False
                
        return True

    def _save_log(self):
        now_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        filename = os.path.join(self.log_dir, f"gesture_log_{self.participant_id}.csv")
        
        duration = time.time() - self.trial_start_time
        # マッチ判定時間を引く（純粋な反応時間にするため）
        reaction_time = max(0, duration - self.match_duration_threshold)

        file_exists = os.path.isfile(filename)
        
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Timestamp", "ParticipantID", "Condition", "TrialNum", 
                    "TargetGesture", "TargetID", "ReactionTime", "TotalTime"
                ])
            
            writer.writerow([
                datetime.now().isoformat(),
                self.participant_id,
                self.condition,
                self.completed_trials + 1,
                self.target_gesture['GestureName'],
                self.current_gesture_id,
                f"{reaction_time:.3f}",
                f"{duration:.3f}"
            ])
        print(f"[GestureTest] Log saved: {self.target_gesture['GestureName']} in {reaction_time:.3f}s")