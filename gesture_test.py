import json
import os
import time
import csv
import random
from datetime import datetime,timedelta,timezone

# 状態定義
STATE_IDLE = "IDLE"
STATE_WAIT_HAND_OPEN = "WAIT_HAND_OPEN" # HandOpen待機中
STATE_COUNTDOWN = "COUNTDOWN"           # 3秒カウントダウン中
STATE_MEASURING = "MEASURING"           # ジェスチャー計測中
STATE_COMPLETED = "COMPLETED"           # 全試行完了

# 定数
DWELL_TIME_THRESHOLD = 0.5 # 秒
MATCH_DISPLAY_DURATION = 0.5 # 秒（MATCH表示を見せる時間）

jst = timezone(timedelta(hours=9))

class Logger:
    def __init__(self, participant_id, condition, handedness="R"):
        self.participant_id = participant_id
        self.condition = condition
        self.handedness = handedness
        
        # logsディレクトリ配下に保存
        self.base_log_dir = os.path.join("logs", "logs_gesture")
        
        if "debug" in participant_id:
            self.log_dir = os.path.join(self.base_log_dir, "debug")
        else:
            self.log_dir = self.base_log_dir
            
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        now_str = datetime.now(jst).strftime("%Y-%m-%d-%H-%M-%S")
        self.log_filepath = os.path.join(self.log_dir, f"log_{participant_id}_{now_str}_gesture_raw.csv")
        
        # CSVヘッダー
        self.headers = [
            "ServerTimestampISO", "ServerTimestamp", "ParticipantID", "Condition", "Handedness", 
            "TrialID", "TargetGesture", "TargetID", 
            "EventType", "EventData", "ClientTimestamp"
        ]
        
        try:
            with open(self.log_filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)
        except Exception as e:
            print(f"Logger Init Error: {e}", flush=True)

    def log_raw(self, trial_id, target_name, target_id, events):
        now = time.time()
        server_ts_iso = datetime.fromtimestamp(now,jst).isoformat()
        server_ts_ms = int(now * 1000)
        
        if not isinstance(events, list):
            if isinstance(events, (dict, str)):
                events = [events]
            else:
                return

        try:
            with open(self.log_filepath, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for event in events:
                    if isinstance(event, str):
                        try:
                            event = json.loads(event)
                        except:
                            continue
                    
                    if not isinstance(event, dict):
                        continue

                    raw_data = event.get('data', {})
                    if isinstance(raw_data, str):
                        try:
                            stripped = raw_data.strip()
                            if stripped.startswith('{') or stripped.startswith('['):
                                raw_data = json.loads(raw_data)
                        except:
                            pass
                    
                    event_data_str = json.dumps(raw_data, ensure_ascii=False)
                    
                    row = [
                        server_ts_iso,
                        server_ts_ms,
                        self.participant_id,
                        self.condition,
                        self.handedness,
                        trial_id,
                        target_name,
                        target_id,
                        event.get('type', 'unknown'),
                        event_data_str,
                        event.get('timestamp', '') 
                    ]
                    writer.writerow(row)
        except Exception as e:
            print(f"Log Error: {e}", flush=True)

class GestureTest:
    def __init__(self, gestures_file):
        self.gestures_file = gestures_file
        self.gestures = self._load_gestures()
        
        self.participant_id = None
        self.condition = None
        self.handedness = "R"
        self.max_trials = 10
        self.trials = [] 
        self.completed_trials = 0
        self.current_gesture_id = None
        
        self.state = STATE_IDLE
        self.logger = None
        
        self.countdown_start_time = None
        self.measure_start_time = None
        
        # マッチ判定用
        self.match_hold_start_time = None # マッチし始めた時刻
        self.match_commit_time = None     # マッチが確定した時刻
        
        self.current_input = {} 

    def _load_gestures(self):
        abs_path = os.path.abspath(self.gestures_file)
        print(f"[GestureTest] Loading gestures from: {abs_path}", flush=True)
        
        if not os.path.exists(abs_path):
            print(f"[GestureTest] CRITICAL ERROR: File not found at {abs_path}", flush=True)
            return []

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                gestures_list = []
                if isinstance(data, list):
                    gestures_list = data
                elif isinstance(data, dict):
                    if 'Gestures' in data and isinstance(data['Gestures'], dict):
                        for id_key, g_data in data['Gestures'].items():
                            if 'ID' not in g_data:
                                try: g_data['ID'] = int(id_key)
                                except: g_data['ID'] = id_key
                            gestures_list.append(g_data)
                    elif 'gestures' in data and isinstance(data['gestures'], list):
                        gestures_list = data['gestures']
                
                valid_gestures = [g for g in gestures_list if isinstance(g, dict) and 'ID' in g]
                if valid_gestures:
                    try: valid_gestures.sort(key=lambda x: int(x['ID']))
                    except: pass 
                    print(f"[GestureTest] Successfully loaded {len(valid_gestures)} gestures.", flush=True)
                return valid_gestures
        except Exception as e:
            print(f"[GestureTest] Error loading gestures JSON: {e}", flush=True)
            return []

    @property
    def target_gesture(self):
        if self.current_gesture_id is None:
            return None
        return next((g for g in self.gestures if g.get('ID') == self.current_gesture_id), None)

    def configure_test(self, participant_id, condition, max_trials, handedness="R"):
        self.participant_id = participant_id
        self.condition = condition
        self.max_trials = int(max_trials)
        self.handedness = handedness
        self.logger = Logger(participant_id, condition, handedness)
        
        if not self.gestures:
            self.gestures = self._load_gestures()
            if not self.gestures:
                self.trials = []
                return

        # 【修正】HandOpen (待機状態) を出題対象から除外
        # GestureNameが 'HandOpen' でないもののIDリストを作成して、そこからランダムに選ぶ
        valid_ids = [g['ID'] for g in self.gestures if g.get('GestureName') != 'HandOpen']

        if not valid_ids:
            # 万が一HandOpenしか登録されていない場合などの安全策（全件対象に戻す）
            print("[GestureTest] Warning: No valid targets found (only HandOpen?). Using all.", flush=True)
            valid_ids = [g['ID'] for g in self.gestures]

        self.trials = [random.choice(valid_ids) for _ in range(self.max_trials)]
        self.completed_trials = 0
        self.state = STATE_IDLE
        
        self.logger.log_raw("None", "None", -1, [{
            "type": "system", 
            "data": {"action": "test_configured", "trials": self.trials},
            "timestamp": int(time.time() * 1000)
        }])
        
        self._next_trial()

    def _next_trial(self):
        if self.completed_trials >= self.max_trials:
            self.state = STATE_COMPLETED
            print("[GestureTest] All trials completed.", flush=True)
            return
            
        self.current_gesture_id = self.trials[self.completed_trials]
        self.state = STATE_WAIT_HAND_OPEN
        
        print(f"[GestureTest] Next trial ({self.completed_trials+1}/{self.max_trials}): GestureID={self.current_gesture_id}", flush=True)
        
        self.countdown_start_time = None
        self.measure_start_time = None
        self.match_hold_start_time = None
        self.match_commit_time = None

    def update_input(self, data):
        """外部からの入力データ更新"""
        if self.state == STATE_IDLE:
            return

        if self.current_input is None:
            self.current_input = {}
        
        try:
            normalized_data = {}
            for k, v in data.items():
                if isinstance(k, str):
                    clean_k = k.strip().upper()
                    normalized_data[clean_k] = v
                else:
                    normalized_data[k] = v

            self.current_input.update(normalized_data)

            if self.logger:
                current_trial = self.completed_trials + 1
                tg = self.target_gesture
                t_name = tg['GestureName'] if tg else "None"
                t_id = tg['ID'] if tg else -1
                
                input_event = {
                    "type": "state_input",
                    "data": normalized_data,
                    "timestamp": int(time.time() * 1000) 
                }
                
                self.logger.log_raw(current_trial, t_name, t_id, [input_event])

            self._update_state_logic()
        except Exception as e:
            print(f"Error in update_input: {e}", flush=True)

    def _update_state_logic(self):
        try:
            if self.state == STATE_WAIT_HAND_OPEN:
                if self._is_hand_open(self.current_input):
                    print(f"[GestureTest] Hand OPEN detected. Moving to COUNTDOWN.", flush=True)
                    self.state = STATE_COUNTDOWN
                    self.countdown_start_time = time.time()
                    
                    if self.logger:
                        self.logger.log_raw(self.completed_trials + 1, 
                                            self.target_gesture['GestureName'], 
                                            self.target_gesture['ID'], 
                                            [{
                                                "type": "state_change", 
                                                "data": {"from": STATE_WAIT_HAND_OPEN, "to": STATE_COUNTDOWN},
                                                "timestamp": int(time.time() * 1000)
                                            }])

            elif self.state == STATE_COUNTDOWN:
                if time.time() - self.countdown_start_time >= 3.0:
                    print(f"[GestureTest] Countdown finished. Waiting for Client Render Trigger...", flush=True)
                    self.state = STATE_MEASURING
                    self.measure_start_time = None 
                    self.match_hold_start_time = None
                    
                    if self.logger:
                        self.logger.log_raw(self.completed_trials + 1, 
                                            self.target_gesture['GestureName'], 
                                            self.target_gesture['ID'], 
                                            [{
                                                "type": "state_change", 
                                                "data": {"from": STATE_COUNTDOWN, "to": STATE_MEASURING},
                                                "timestamp": int(time.time() * 1000)
                                            }])
                
            elif self.state == STATE_MEASURING:
                if self.measure_start_time is None:
                    return

                # マッチ確定後の表示期間処理
                if self.match_commit_time is not None:
                    if time.time() - self.match_commit_time >= MATCH_DISPLAY_DURATION:
                         self._process_match()
                    return

                target = self.target_gesture
                is_matching = self._check_match(target, self.current_input)
                
                if is_matching:
                    if self.match_hold_start_time is None:
                        # マッチ開始！維持計測スタート
                        self.match_hold_start_time = time.time()
                    
                    # 0.5秒維持できたかチェック
                    elapsed = time.time() - self.match_hold_start_time
                    if elapsed >= DWELL_TIME_THRESHOLD:
                        # 即座に遷移せず、確定時刻を記録して待機に入る
                        self.match_commit_time = time.time()
                        print(f"[GestureTest] Match Committed (Wait for display).", flush=True)
                else:
                    # マッチが途切れたらリセット
                    self.match_hold_start_time = None

        except Exception as e:
            print(f"Error in _update_state_logic: {e}", flush=True)

    def _is_hand_open(self, input_data):
        fingers = ['T', 'I', 'M', 'R', 'P']
        for finger in fingers:
            val = input_data.get(finger)
            if isinstance(val, str):
                val = val.strip().upper()
            if val != 'OPEN':
                return False
        return True

    def _check_match(self, target, input_data):
        if not target: return False
        
        target_states = target.get('State', {})
        if not target_states: target_states = target

        for finger in ['T', 'I', 'M', 'R', 'P']:
            target_val_or_list = target_states.get(finger)
            input_val = input_data.get(finger)
            
            if isinstance(input_val, str):
                input_val = input_val.strip().upper()
            
            if target_val_or_list is None:
                continue

            if isinstance(target_val_or_list, list):
                if input_val not in target_val_or_list:
                    return False
            else:
                t_str = str(target_val_or_list).strip().upper()
                if t_str != input_val:
                    return False
        return True

    def _process_match(self):
        # 反応時間 (RT) の計算
        if self.match_hold_start_time:
             rt_end_time = self.match_hold_start_time
        else:
             rt_end_time = self.match_commit_time - DWELL_TIME_THRESHOLD if self.match_commit_time else time.time()

        duration = (rt_end_time - self.measure_start_time) * 1000 if self.measure_start_time else 0
        
        print(f"[GestureTest] Match Processed! Trial {self.completed_trials + 1} done. RT: {duration:.2f}ms", flush=True)
        
        if self.logger:
             self.logger.log_raw(self.completed_trials + 1, 
                                self.target_gesture['GestureName'], 
                                self.target_gesture['ID'], 
                                [{
                                    "type": "state_change", 
                                    "data": {
                                        "from": STATE_MEASURING, 
                                        "to": STATE_COMPLETED if self.completed_trials + 1 >= self.max_trials else "NEXT_TRIAL",
                                        "rt_ms": duration
                                    },
                                    "timestamp": int(time.time() * 1000)
                                }])

        self.completed_trials += 1
        self._next_trial()

    def check_state(self):
        try:
            # 時間経過チェック (COUNTDOWN)
            if self.state == STATE_COUNTDOWN and self.countdown_start_time:
                if time.time() - self.countdown_start_time >= 3.0:
                    self.state = STATE_MEASURING
                    self.measure_start_time = None
                    self.match_hold_start_time = None

            # ★追加: MEASURING中の時間経過チェック (ポーリング駆動での遷移)
            if self.state == STATE_MEASURING:
                # 1. マッチ確定後の表示時間終了チェック
                if self.match_commit_time is not None:
                     if time.time() - self.match_commit_time >= MATCH_DISPLAY_DURATION:
                         self._process_match()
                
                # 2. 入力が来なくても、維持時間が経過していたら確定させるチェック
                # (直前の状態が維持されていると仮定する)
                elif self.match_hold_start_time is not None:
                     elapsed = time.time() - self.match_hold_start_time
                     if elapsed >= DWELL_TIME_THRESHOLD:
                         self.match_commit_time = time.time()
                         print(f"[GestureTest] Match Committed (via check_state).", flush=True)

            remaining = 0
            if self.state == STATE_COUNTDOWN and self.countdown_start_time:
                elapsed = time.time() - self.countdown_start_time
                remaining = max(0.0, 3.0 - elapsed)
            
            # 維持進捗の計算
            progress = 0.0
            if self.state == STATE_MEASURING:
                if self.match_commit_time is not None:
                    progress = 1.0 
                elif self.match_hold_start_time:
                    elapsed = time.time() - self.match_hold_start_time
                    progress = min(1.0, elapsed / DWELL_TIME_THRESHOLD)

            response = {
                "state": self.state,
                "current_trial": self.completed_trials + 1,
                "total_trials": self.max_trials,
                "current_input": self.current_input
            }
            
            if self.state == STATE_COUNTDOWN:
                response["countdown_remaining"] = remaining
                
            if self.state == STATE_MEASURING:
                tg = self.target_gesture
                response["target"] = tg 
                response["is_match"] = (self.match_commit_time is not None)
                response["match_progress"] = progress 
                
            return response
        except Exception as e:
            print(f"Error in check_state: {e}", flush=True)
            return {"state": "ERROR", "error": str(e)}

    def log_client_events(self, events):
        if self.logger and events:
            if isinstance(events, str):
                try: events = json.loads(events)
                except: return

            if isinstance(events, dict):
                events = [events]

            current_trial = self.completed_trials + 1
            tg = self.target_gesture
            t_name = tg['GestureName'] if tg else "None"
            t_id = tg['ID'] if tg else -1
            self.logger.log_raw(current_trial, t_name, t_id, events)

            for event in events:
                if not isinstance(event, dict): continue

                if event.get('type') == 'system':
                    data = event.get('data', {})
                    if isinstance(data, str):
                         try: data = json.loads(data)
                         except: pass
                             
                    if isinstance(data, dict) and data.get('action') == "stimulus_rendered_on_client":
                         if self.state == STATE_MEASURING and self.measure_start_time is None:
                             self.measure_start_time = time.time()
                             print(f"[GestureTest] Client Render Trigger Received. Timer STARTED at {self.measure_start_time}", flush=True)