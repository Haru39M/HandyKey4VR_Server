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

class Logger:
    def __init__(self, participant_id, condition, handedness="R"):
        self.participant_id = participant_id
        self.condition = condition
        self.handedness = handedness
        
        self.base_log_dir = "logs_gesture"
        
        # Debugモード判定
        if "debug" in participant_id:
            self.log_dir = os.path.join(self.base_log_dir, "debug")
        else:
            self.log_dir = self.base_log_dir
            
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        now_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        # Rawログとして保存
        self.log_filepath = os.path.join(self.log_dir, f"log_{participant_id}_{now_str}_gesture_raw.csv")
        
        # Header設定 (ClientTimestampを末尾に追加)
        self._init_csv(self.log_filepath, [
            "ServerTimestamp", "ParticipantID", "Condition", "Handedness", 
            "TrialID", "TargetGesture", "TargetID", 
            "EventType", "EventData", "ClientTimestamp"
        ])

    def _init_csv(self, filepath, header):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)

    def log_raw(self, trial_id, target_name, target_id, events):
        """クライアントからのイベント群、またはサーバーイベントをRawログに書き込む"""
        if not events: return
        
        with open(self.log_filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for e in events:
                # dataフィールドが辞書やリストの場合はJSON文字列化してCSV崩れを防ぐ
                raw_data = e.get('data')
                if isinstance(raw_data, (dict, list)):
                    data_str = json.dumps(raw_data)
                else:
                    data_str = str(raw_data)

                writer.writerow([
                    datetime.now().isoformat(), # ServerTimestamp
                    self.participant_id,
                    self.condition,
                    self.handedness,
                    target_name,
                    trial_id,
                    target_id,
                    e.get('type'),
                    data_str,
                    e.get('timestamp') # ClientTimestamp (JSのDate.now())
                ])

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
        self.handedness = "R"
        self.max_trials = 10
        self.completed_trials = 0
        self.state = STATE_IDLE
        
        # タイマー管理
        self.countdown_start_time = 0.0
        self.measure_start_time = 0.0
        self.match_start_time = None
        self.match_duration_threshold = 0.5 # チャタリング防止時間
        
        # Logger
        self.logger = None
            
        self._load_gestures(gestures_path)

    def _load_gestures(self, path):
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
        
        # Loggerの初期化
        self.logger = Logger(participant_id, condition, handedness)
        
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
                    # 完了 -> ログ保存処理呼び出し -> 次へ
                    self._process_trial_completion()
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

    def _process_trial_completion(self):
        """試行完了時の計算とLoggerへの委譲（サーバーサイドイベントとして記録）"""
        duration = time.time() - self.measure_start_time
        total_time_str = f"{duration:.3f}"

        if self.logger:
            # サーバー側で検知した完了イベントをRawログに記録
            self.logger.log_raw(
                trial_id=self.completed_trials + 1,
                target_name=self.target_gesture['GestureName'],
                target_id=self.current_gesture_id,
                events=[{
                    "type": "server_trial_completed",
                    "data": { "total_time": total_time_str },
                    "timestamp": int(time.time() * 1000) # Server time in ms
                }]
            )

    def log_client_events(self, events):
        """app.pyから渡されたクライアントイベントリストをLoggerに記録する"""
        if self.logger and events:
            # 現在の試行情報を取得（未設定時は"None"などをセット）
            current_trial = self.completed_trials + 1
            t_name = self.target_gesture['GestureName'] if self.target_gesture else "None"
            t_id = self.current_gesture_id if self.current_gesture_id else "None"
            
            self.logger.log_raw(current_trial, t_name, t_id, events)