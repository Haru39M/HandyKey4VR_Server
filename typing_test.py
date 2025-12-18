import re
import time
import difflib
import csv
import os
from datetime import datetime
from collections import defaultdict

class Logger:
    def __init__(self, participant_id, condition):
        self.participant_id = participant_id
        self.condition = condition
        
        # タイムスタンプ生成 (YYYY-MM-DD-hh-mm-ss)
        now_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.log_dir = "logs"
        
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        # ファイルパス設定
        # 1. サマリーログ (文単位)
        self.summary_path = os.path.join(self.log_dir, f"log_{participant_id}_{now_str}_summary.csv")
        # 2. Rawログ (操作単位)
        self.raw_path = os.path.join(self.log_dir, f"log_{participant_id}_{now_str}_raw.csv")

        # ヘッダー書き込み
        self._init_csv(self.summary_path, [
            "Timestamp", "ParticipantID", "Condition", "TrialID", 
            "TargetPhrase", "InputPhrase", 
            "CompletionTime", "CharCount", "ErrorDist", "BackspaceCount"
        ])
        
        self._init_csv(self.raw_path, [
            "Timestamp", "ParticipantID", "Condition", "TrialID",
            "EventType", "EventData", "ClientTimestamp"
        ])

    def _init_csv(self, filepath, header):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)

    def log_summary(self, data):
        """文単位の完了ログ"""
        with open(self.summary_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                self.participant_id,
                self.condition,
                data.get('trial_id'),
                data.get('target'),
                data.get('input'),
                data.get('time'),
                data.get('char_count'),
                data.get('error_dist'),
                data.get('backspace_count')
            ])

    def log_raw(self, trial_id, events):
        """フロントエンドから送られてきたイベントリストを一括書き込み"""
        if not events: return
        
        with open(self.raw_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for e in events:
                writer.writerow([
                    datetime.now().isoformat(),
                    self.participant_id,
                    self.condition,
                    trial_id,
                    e.get('type'),      # keydown, predict, select...
                    e.get('data'),      # key='a', word='apple'...
                    e.get('timestamp')  # client side timestamp
                ])

class TypingTest:
    def __init__(self):
        self.phrases = []
        self.total_sentence = 0
        self.current_sentence_index = 0
        self.reference_text = "ReferenceText"
        self.reference_words = []
        
        # 設定 & ロガー
        self.logger = None
        self.participant_id = "test"
        self.condition = "default"
        self.max_sentences = 5
        self.completed_sentences_count = 0
        
        # 状態
        self.phrase_start_time = 0.0
        self.backspace_count_phrase = 0 # フレーズ内のBS回数

    def loadPhraseSet(self, dataset_path: str):
        try:
            with open(dataset_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content_cleaned = re.sub(r'\[source:\s*\d+\]', '', content)
            self.phrases = [line.strip() for line in content_cleaned.split('\n') if line.strip()]
            self.total_sentence = len(self.phrases)
            self.current_sentence_index = 0
            print(f"[TypingTest] Loaded {self.total_sentence} phrases")
        except FileNotFoundError:
            self.phrases = ["Error loading phrases"]
            self.total_sentence = 1

    def configure_test(self, participant_id, condition, max_sentences):
        self.participant_id = participant_id
        self.condition = condition
        self.max_sentences = int(max_sentences)
        self.completed_sentences_count = 0
        self.current_sentence_index = 0
        
        # ロガーの初期化 (ここでファイルが作成されます)
        self.logger = Logger(participant_id, condition)

    def loadReferenceText(self):
        if not self.phrases:
            self.reference_text = "No phrases loaded."
            self.reference_words = []
            return

        if self.completed_sentences_count >= self.max_sentences:
            self.reference_text = "TEST_FINISHED"
            self.reference_words = []
            return

        if self.current_sentence_index >= self.total_sentence:
            self.current_sentence_index = 0

        self.reference_text = self.phrases[self.current_sentence_index]
        self.reference_words = self.reference_text.split()
        self.current_sentence_index += 1
        
        # 計測リセット
        self.phrase_start_time = time.time()
        self.backspace_count_phrase = 0

    def getReferenceText(self) -> str:
        return self.reference_text

    def log_client_events(self, events):
        """フロントエンドからのRawログを保存"""
        if self.logger:
            # 現在挑戦中のTrial ID (完了数 + 1) を紐付ける
            current_trial_id = self.completed_sentences_count + 1
            self.logger.log_raw(current_trial_id, events)
            
            # サーバー側で検知すべきイベント(Backspace等)をここでカウントしてもよい
            for e in events:
                if e.get('type') == 'keydown' and e.get('data') == 'Backspace':
                    self.backspace_count_phrase += 1

    def check_input(self, input_words: list[str]) -> dict:
        results = []
        all_correct_so_far = True
        
        for i, word in enumerate(input_words):
            is_correct = False
            if i < len(self.reference_words):
                if word.lower() == self.reference_words[i].lower():
                    is_correct = True
            if not is_correct:
                all_correct_so_far = False
            results.append({"word": word, "is_correct": is_correct})

        is_completed = all_correct_so_far and (len(input_words) == len(self.reference_words))

        if is_completed:
            self._save_summary_log(input_words)
            self.completed_sentences_count += 1

        return {
            "results": results,
            "is_completed": is_completed,
            "is_all_finished": self.reference_text == "TEST_FINISHED"
        }

    def _save_summary_log(self, input_words):
        if not self.logger: return
        
        input_phrase = " ".join(input_words)
        duration = time.time() - self.phrase_start_time
        dist = self._levenshtein_distance(self.reference_text, input_phrase)
        
        self.logger.log_summary({
            'trial_id': self.completed_sentences_count + 1,
            'target': self.reference_text,
            'input': input_phrase,
            'time': f"{duration:.3f}",
            'char_count': len(input_phrase),
            'error_dist': dist,
            'backspace_count': self.backspace_count_phrase
        })
        print(f"[TypingTest] Trial {self.completed_sentences_count + 1} Logged.")

    def _levenshtein_distance(self, s1, s2):
        if len(s1) < len(s2): return self._levenshtein_distance(s2, s1)
        if len(s2) == 0: return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]