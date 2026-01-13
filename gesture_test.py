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
        
        if "debug" in participant_id:
            self.log_dir = os.path.join(self.base_log_dir, "debug")
        else:
            self.log_dir = self.base_log_dir
            
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        now_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.log_filepath = os.path.join(self.log_dir, f"log_{participant_id}_{now_str}_gesture_raw.csv")
        
        self.headers = [
            "ServerTimestamp", "ParticipantID", "Condition", "Handedness", 
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
        server_ts = datetime.now().isoformat()
        try:
            with open(self.log_filepath, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for event in events:
                    event_data_str = json.dumps(event.get('data', {}))
                    row = [
                        server_ts,
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
        self.match_start_time = None
        self.current_input = {} 

    def _load_gestures(self):
        # パス解決のログ（デバッグ用）
        abs_path = os.path.abspath(self.gestures_file)
        print(f"[GestureTest] Loading gestures from: {abs_path}", flush=True)
        
        if not os.path.exists(abs_path):
            print(f"[GestureTest] CRITICAL ERROR: File not found at {abs_path}", flush=True)
            return []

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                gestures_list = []
                
                # Case 1: Rootがリストの場合（古い形式）
                if isinstance(data, list):
                    gestures_list = data
                
                # Case 2: Rootが辞書の場合（新しい形式 "Gestures": {...}）
                elif isinstance(data, dict):
                    # "Gestures" キーが存在するか確認
                    if 'Gestures' in data and isinstance(data['Gestures'], dict):
                        for id_key, g_data in data['Gestures'].items():
                            # 辞書データにIDが含まれていない場合、キーをIDとして埋め込む
                            if 'ID' not in g_data:
                                try:
                                    g_data['ID'] = int(id_key) # 数値として扱えるならintに
                                except:
                                    g_data['ID'] = id_key      # 無理なら文字列のまま
                            gestures_list.append(g_data)
                    
                    # 古い形式 "gestures": [...] の場合
                    elif 'gestures' in data and isinstance(data['gestures'], list):
                        gestures_list = data['gestures']
                    
                    else:
                        print(f"[GestureTest] Warning: Valid 'Gestures' key not found in JSON dict.", flush=True)

                # 'ID'キーを持つ要素のみを有効とする
                valid_gestures = [g for g in gestures_list if isinstance(g, dict) and 'ID' in g]
                
                if not valid_gestures:
                    print(f"[GestureTest] Warning: No valid gestures found (checked for 'ID' key).", flush=True)
                else:
                    # ID順にソートしておく（見やすさのため）
                    try:
                        valid_gestures.sort(key=lambda x: int(x['ID']))
                    except:
                        pass # IDが混在している場合はソートしない
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
            print("[GestureTest] Error: No gestures loaded. Cannot start test. Retrying load...", flush=True)
            self.gestures = self._load_gestures()
            if not self.gestures:
                self.trials = []
                return

        all_ids = [g['ID'] for g in self.gestures]
        self.trials = [random.choice(all_ids) for _ in range(self.max_trials)]
        self.completed_trials = 0
        self.state = STATE_IDLE
        
        print(f"[GestureTest] Configured. ID={participant_id}, Cond={condition}, Trials={self.trials}", flush=True)

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
        
        print(f"[GestureTest] Next trial ({self.completed_trials+1}/{self.max_trials}): GestureID={self.current_gesture_id}, State={self.state}", flush=True)
        
        self.countdown_start_time = None
        self.measure_start_time = None
        self.match_start_time = None

    def update_input(self, data):
        """外部からの入力データ更新"""
        if self.state == STATE_IDLE:
            print(f"[GestureTest] WARNING: Received input but State is IDLE. Please START the test first.", flush=True)
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
                # else: pass
                    
            elif self.state == STATE_COUNTDOWN:
                if time.time() - self.countdown_start_time >= 3.0:
                    print(f"[GestureTest] Countdown finished. Moving to MEASURING.", flush=True)
                    self.state = STATE_MEASURING
                    self.measure_start_time = time.time()
                
            elif self.state == STATE_MEASURING:
                target = self.target_gesture
                if self._check_match(target, self.current_input):
                    if self.match_start_time is None:
                        self.match_start_time = time.time()
                    self._process_match()
                else:
                    self.match_start_time = None
        except Exception as e:
            print(f"Error in _update_state_logic: {e}", flush=True)

    def _is_hand_open(self, input_data):
        fingers = ['T', 'I', 'M', 'R', 'P']
        for finger in fingers:
            raw_val = input_data.get(finger)
            val = raw_val
            if isinstance(val, str):
                val = val.strip().upper()
                
            if val != 'OPEN':
                if self.state == STATE_WAIT_HAND_OPEN:
                    # デバッグ用: 頻繁に出る場合はコメントアウト
                    print(f"[GestureTest] Hand Check Failed. Finger: {finger}, Value: '{raw_val}' -> Normalized: '{val}'", flush=True)
                return False
        return True

    def _check_match(self, target, input_data):
        if not target: return False
        
        # 新しいJSON構造では "State" キーの下に指の状態がある
        target_states = target.get('State', {})
        # もし "State" がなければ、ターゲット自体がフラットな辞書である可能性も考慮（古い形式への後方互換）
        if not target_states:
             target_states = target

        for finger in ['T', 'I', 'M', 'R', 'P']:
            # ターゲットの値は文字列 "OPEN" または リスト ["OPEN", "TOUCH"] の可能性がある
            target_val_or_list = target_states.get(finger)
            input_val = input_data.get(finger)
            
            # 入力の正規化
            if isinstance(input_val, str):
                input_val = input_val.strip().upper()
            
            # ターゲット定義がない指は無視（今回は全ての指が定義されている前提）
            if target_val_or_list is None:
                continue

            # 判定ロジック
            if isinstance(target_val_or_list, list):
                # リストの場合: 入力値がリストのいずれかと一致すればOK
                # リスト内の要素も大文字前提とする（必要ならここで正規化ループ）
                if input_val not in target_val_or_list:
                    return False
            else:
                # 文字列の場合: 完全一致チェック
                t_str = str(target_val_or_list).strip().upper()
                if t_str != input_val:
                    return False
                    
        return True

    def _process_match(self):
        print(f"[GestureTest] Match confirmed! Trial {self.completed_trials + 1} completed.", flush=True)
        self._process_trial_completion()
        self.completed_trials += 1
        self._next_trial()

    def check_state(self):
        try:
            # ★修正: ポーリング時にも時間経過による状態遷移をチェックする
            if self.state == STATE_COUNTDOWN and self.countdown_start_time:
                if time.time() - self.countdown_start_time >= 3.0:
                    print(f"[GestureTest] Countdown finished (in check_state). Moving to MEASURING.", flush=True)
                    self.state = STATE_MEASURING
                    self.measure_start_time = time.time()

            remaining = 0
            if self.state == STATE_COUNTDOWN and self.countdown_start_time:
                elapsed = time.time() - self.countdown_start_time
                remaining = max(0.0, 3.0 - elapsed)
            
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
                response["is_match"] = (self.match_start_time is not None)
                
            return response
        except Exception as e:
            print(f"Error in check_state: {e}", flush=True)
            return {"state": "ERROR", "error": str(e)}

    def _process_trial_completion(self):
        pass

    def log_client_events(self, events):
        if self.logger and events:
            current_trial = self.completed_trials + 1
            tg = self.target_gesture
            t_name = tg['GestureName'] if tg else "None"
            t_id = tg['ID'] if tg else -1
            self.logger.log_raw(current_trial, t_name, t_id, events)