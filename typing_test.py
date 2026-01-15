import re
import time
import csv
import os
import random
from datetime import datetime
# from collections import defaultdict

jst = datetime.timezone(datetime.timedelta(hours=9))

class Logger:
    def __init__(self, participant_id, condition, handedness="R"):
        self.participant_id = participant_id
        self.condition = condition
        self.handedness = handedness
        
        # 【修正】logsディレクトリ配下に保存するように変更
        self.base_log_dir = os.path.join("logs", "logs_typing")
        
        # Debugモード判定
        if "debug" in participant_id:
            self.log_dir = os.path.join(self.base_log_dir, "debug")
        else:
            self.log_dir = self.base_log_dir
            
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        now_str = datetime.now(jst).strftime("%Y-%m-%d-%H-%M-%S")
        self.raw_path = os.path.join(self.log_dir, f"log_{participant_id}_{now_str}_typing_raw.csv")
        
        # Headerに PhraseID を追加
        self._init_csv(self.raw_path, [
            "Timestamp", "ParticipantID", "Condition", "Handedness", "TrialID", "PhraseID",
            "EventType", "EventData", "ClientTimestamp"
        ])

    def _init_csv(self, filepath, header):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)

    def log_raw(self, trial_id, phrase_id, events):
        if not events: return
        with open(self.raw_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for e in events:
                writer.writerow([
                    datetime.now(jst).isoformat(),
                    self.participant_id,
                    self.condition,
                    self.handedness,
                    trial_id,
                    phrase_id, # PhraseIDを記録
                    e.get('type'),
                    e.get('data'),
                    e.get('timestamp')
                ])

class TypingTest:
    def __init__(self):
        self.phrases = []
        self.total_sentence = 0
        self.current_sentence_index = 0
        self.reference_text = "ReferenceText"
        self.reference_words = []
        self.current_phrase_id = -1 # 現在のフレーズID (phrases2.txtの行番号)
        
        self.test_phrase_queue = [] # (id, phrase) のタプルのリスト
        
        self.logger = None
        self.participant_id = "test"
        self.condition = "default"
        self.handedness = "R"
        self.max_sentences = 5
        self.completed_sentences_count = 0
        
        self.phrase_start_time = 0.0
        self.backspace_count_phrase = 0

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

    def configure_test(self, participant_id, condition, max_sentences, handedness="R"):
        self.participant_id = participant_id
        self.condition = condition
        self.max_sentences = int(max_sentences)
        self.handedness = handedness
        self.completed_sentences_count = 0
        self.current_sentence_index = 0
        self.logger = Logger(participant_id, condition, handedness)
        
        if self.phrases:
            count = min(len(self.phrases), self.max_sentences)
            # インデックス(PhraseID)とフレーズのペアを作成してランダムサンプリング
            indexed_phrases = list(enumerate(self.phrases))
            self.test_phrase_queue = random.sample(indexed_phrases, count)
            print(f"[TypingTest] Selected {count} phrases randomly for this session.")
        else:
            self.test_phrase_queue = []

    def loadReferenceText(self):
        if not self.test_phrase_queue:
            self.reference_text = "No phrases loaded."
            self.reference_words = []
            return

        if self.completed_sentences_count >= self.max_sentences:
            self.reference_text = "TEST_FINISHED"
            self.reference_words = []
            return

        if self.current_sentence_index < len(self.test_phrase_queue):
            # キューから (ID, Text) を取り出す
            self.current_phrase_id, self.reference_text = self.test_phrase_queue[self.current_sentence_index]
        else:
            self.reference_text = "TEST_FINISHED"
            self.reference_words = []
            return

        self.reference_words = self.reference_text.split()
        self.current_sentence_index += 1
        
        self.phrase_start_time = time.time()
        self.backspace_count_phrase = 0

    def getReferenceText(self) -> str:
        return self.reference_text

    def log_client_events(self, events):
        if self.logger:
            current_trial_id = self.completed_sentences_count + 1
            self.logger.log_raw(current_trial_id, self.current_phrase_id, events)
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
            self.completed_sentences_count += 1

        return {
            "results": results,
            "is_completed": is_completed,
            "is_all_finished": self.reference_text == "TEST_FINISHED"
        }