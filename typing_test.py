import re
import time
import difflib
import csv
import os
import random
from datetime import datetime
from collections import defaultdict

class Logger:
    def __init__(self, participant_id, condition, handedness="R"):
        self.participant_id = participant_id
        self.condition = condition
        self.handedness = handedness
        
        now_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        
        self.base_log_dir = "logs_typing"
        
        # Debugモード判定
        if "debug" in participant_id:
            self.log_dir = os.path.join(self.base_log_dir, "debug")
        else:
            self.log_dir = self.base_log_dir
            
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        self.summary_path = os.path.join(self.log_dir, f"log_{participant_id}_{now_str}_typing.csv")
        self.raw_path = os.path.join(self.log_dir, f"log_{participant_id}_{now_str}_typing_raw.csv")

        self._init_csv(self.summary_path, [
            "Timestamp", "ParticipantID", "Condition", "Handedness", "TrialID", 
            "TargetPhrase", "InputPhrase", 
            "CompletionTime", "CharCount", "WPM", "ErrorDist", "BackspaceCount"
        ])
        
        self._init_csv(self.raw_path, [
            "Timestamp", "ParticipantID", "Condition", "Handedness", "TrialID",
            "EventType", "EventData", "ClientTimestamp"
        ])

    def _init_csv(self, filepath, header):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)

    def log_summary(self, data):
        with open(self.summary_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                self.participant_id,
                self.condition,
                self.handedness,
                data.get('trial_id'),
                data.get('target'),
                data.get('input'),
                data.get('time'),
                data.get('char_count'),
                data.get('wpm'),
                data.get('error_dist'),
                data.get('backspace_count')
            ])

    def log_raw(self, trial_id, events):
        if not events: return
        with open(self.raw_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for e in events:
                writer.writerow([
                    datetime.now().isoformat(),
                    self.participant_id,
                    self.condition,
                    self.handedness,
                    trial_id,
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
        
        self.test_phrase_queue = [] # 今回のテストで使用するフレーズのリスト
        
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
        
        # ランダムにフレーズを選択（重複なし）
        if self.phrases:
            # max_sentencesが総数より多い場合は全数を使う
            count = min(len(self.phrases), self.max_sentences)
            self.test_phrase_queue = random.sample(self.phrases, count)
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

        # キューから取得（current_sentence_index を使用）
        if self.current_sentence_index < len(self.test_phrase_queue):
            self.reference_text = self.test_phrase_queue[self.current_sentence_index]
        else:
            # 万が一キューが尽きた場合
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
            self.logger.log_raw(current_trial_id, events)
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
        
        char_count = len(input_phrase)
        wpm = 0.0
        if duration > 0:
            wpm = (char_count / 5.0) / (duration / 60.0)
            
        dist = self._levenshtein_distance(self.reference_text, input_phrase)
        
        self.logger.log_summary({
            'trial_id': self.completed_sentences_count + 1,
            'target': self.reference_text,
            'input': input_phrase,
            'time': f"{duration:.3f}",
            'char_count': char_count,
            'wpm': f"{wpm:.2f}",
            'error_dist': dist,
            'backspace_count': self.backspace_count_phrase
        })
        print(f"[TypingTest] Logged: WPM={wpm:.2f}")

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