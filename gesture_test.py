import json
import os
import time
import csv
import random
from datetime import datetime

# 状態定義
STATE_IDLE = "IDLE"
STATE_WAIT_HAND_OPEN = "WAIT_HAND_OPEN" # HandOpen待機中
STATE_COUNTDOWN = "COUNTDOWN"           # 3秒カウントダウン中
STATE_MEASURING = "MEASURING"           # ジェスチャー計測中
STATE_COMPLETED = "COMPLETED"           # 全試行完了

class GestureTest:
    def __init__(self, gestures_path='gestures/gestures.json'):
        self.gestures_data = {}
        self.gesture_list = []
        self.target_gesture = None
        self.current_gesture_id = None
        
        # デバイスからの現在の入力状態
        self.current_device_state = {
            "T": "OPEN", "I": "OPEN", "M": "OPEN", "R": "OPEN", "P": "OPEN"
        }
        
        # テスト設定
        self.participant_id = "test"
        self.condition = "default"
        self.handedness = "R" # デフォルト
        self.max_trials = 10
        self.completed_trials = 0
        self.state = STATE_IDLE
        
        # タイマー管理
        self.countdown_start_time = 0.0
        self.measure_start_time = 0.0
        self.match_start_time = None
        self.match_duration_threshold = 0.5 # チャタリング防止時間
        
        # ログ用
        self.base_log_dir = "logs_gesture"
        self.log_filepath = ""
            
        self.load_gestures(gestures_path)

    def load_gestures(self, path):
        if not os.path.exists(path):
            print(f"[GestureTest] Error: {path} not found.")
            return
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.gestures_data = data.get("Gestures", {})
            self.gesture_list = list(self.gestures_data.keys())

    def configure_test(self, participant_id, condition, max_trials, handedness="R"):
        self.participant_id = participant_id
        self.condition = condition
        self.max_trials = int(max_trials)
        self.handedness = handedness
        self.completed_trials = 0
        
        # ログ保存先の決定
        if self.participant_id == "debug":
            current_log_dir = os.path.join(self.base_log_dir, "debug")
        else:
            current_log_dir = self.base_log_dir
            
        if not os.path.exists(current_log_dir):
            os.makedirs(current_log_dir)

        now_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.log_filepath = os.path.join(current_log_dir, f"log_{participant_id}_{now_str}_gesture.csv")
        self._init_log()
        
        self._start_wait_hand_open()

    def update_input(self, input_state):
        for key, val in input_state.items():
            if key in self.current_device_state:
                self.current_device_state[key] = val

    def check_state(self):
        """現在の状態を確認し、ステート遷移を行う"""
        
        if self.state == STATE_IDLE or self.state == STATE_COMPLETED:
            return self._build_status_response()

        # 1. HandOpen待機
        if self.state == STATE_WAIT_HAND_OPEN:
            if self._is_hand_open():
                # HandOpen検知 -> カウントダウンへ
                self.state = STATE_COUNTDOWN
                self.countdown_start_time = time.time()
                self._pick_next_target()

        # 2. カウントダウン (3秒)
        elif self.state == STATE_COUNTDOWN:
            elapsed = time.time() - self.countdown_start_time
            if elapsed >= 3.0:
                # カウントダウン終了 -> 計測開始
                self.state = STATE_MEASURING
                self.measure_start_time = time.time()
                self.match_start_time = None

        # 3. 計測中
        elif self.state == STATE_MEASURING:
            if self._is_matching_target():
                if self.match_start_time is None:
                    self.match_start_time = time.time()
                elif time.time() - self.match_start_time >= self.match_duration_threshold:
                    # 完了 -> ログ保存 -> 次へ
                    self._save_log()
                    self.completed_trials += 1
                    
                    if self.completed_trials >= self.max_trials:
                        self.state = STATE_COMPLETED
                    else:
                        self._start_wait_hand_open()
            else:
                self.match_start_time = None

        return self._build_status_response()

    def _start_wait_hand_open(self):
        self.state = STATE_WAIT_HAND_OPEN
        self.target_gesture = None 

    def _pick_next_target(self):
        candidates = [gid for gid in self.gesture_list if self.gestures_data[gid]['GestureName'] != "HandOpen"]
        if not candidates: candidates = self.gesture_list 
        
        self.current_gesture_id = random.choice(candidates)
        self.target_gesture = self.gestures_data[self.current_gesture_id]
        print(f"[GestureTest] Next Target Selected: {self.target_gesture['GestureName']}")

    def _is_hand_open(self):
        for f in ["T", "I", "M", "R", "P"]:
            if self.current_device_state[f] != "OPEN":
                return False
        return True

    def _is_matching_target(self):
        if not self.target_gesture: return False
        
        target_state = self.target_gesture["State"]
        if self.target_gesture['GestureName'] == "Neutral":
            if self._is_hand_open(): return False

        for f in ["T", "I", "M", "R", "P"]:
            current_val = self.current_device_state.get(f)
            allowed = target_state.get(f, [])
            if current_val not in allowed:
                return False
        return True

    def _build_status_response(self):
        response = {
            "state": self.state,
            "current_input": self.current_device_state,
            "progress": f"{self.completed_trials} / {self.max_trials}",
            "is_running": self.state != STATE_COMPLETED and self.state != STATE_IDLE
        }
        
        if self.state == STATE_COUNTDOWN:
            elapsed = time.time() - self.countdown_start_time
            remaining = max(0, 3.0 - elapsed)
            response["countdown_remaining"] = remaining
            
        if self.state == STATE_MEASURING:
            response["target"] = self.target_gesture
            response["is_match"] = (self.match_start_time is not None)
            
        return response

    def _init_log(self):
        with open(self.log_filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Timestamp", "ParticipantID", "Condition", "Handedness", "TrialNum", 
                "TargetGesture", "TargetID", "ReactionTime", "TotalTime"
            ])

    def _save_log(self):
        duration = time.time() - self.measure_start_time
        reaction_time = max(0, duration - self.match_duration_threshold)
        
        with open(self.log_filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                self.participant_id,
                self.condition,
                self.handedness,
                self.completed_trials + 1,
                self.target_gesture['GestureName'],
                self.current_gesture_id,
                f"{reaction_time:.3f}",
                f"{duration:.3f}"
            ])
        print(f"[GestureTest] Log saved: {reaction_time:.3f}s")