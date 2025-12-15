import re
import time
import difflib
import csv
import os
from datetime import datetime
from collections import defaultdict

class TypingTest:
    def __init__(self):
        self.phrases = []
        self.total_sentence = 0
        self.current_sentence_index = 0
        self.reference_text = "ReferenceText"
        self.reference_words = []
        
        # 設定
        self.participant_id = "test_user"
        self.condition = "default"
        self.max_sentences = 5 # デフォルト
        self.completed_sentences_count = 0
        
        # 計測用
        self.start_time = 0.0
        self.phrase_start_time = 0.0 # フレーズごとの開始時間
        self.miss_counts = defaultdict(int)
        self.backspace_count = 0 # バックスペース回数

    def loadPhraseSet(self, dataset_path: str):
        try:
            with open(dataset_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content_cleaned = re.sub(r'\[source:\s*\d+\]', '', content)
            self.phrases = [line.strip() for line in content_cleaned.split('\n') if line.strip()]
            self.total_sentence = len(self.phrases)
            self.current_sentence_index = 0
            print(f"[TypingTest] Loaded {self.total_sentence} phrases from {dataset_path}")
        except FileNotFoundError:
            print(f"[TypingTest] Error: File not found {dataset_path}")
            self.phrases = ["Error"]
            self.total_sentence = 1

    def configure_test(self, participant_id, condition, max_sentences):
        """テスト設定を更新"""
        self.participant_id = participant_id
        self.condition = condition
        self.max_sentences = int(max_sentences)
        self.completed_sentences_count = 0
        self.current_sentence_index = 0 # 最初から

    def loadReferenceText(self):
        """次のフレーズをロード"""
        if not self.phrases:
            self.reference_text = "No phrases loaded."
            self.reference_words = []
            return

        # 全フレーズ完了または設定数に達したら終了
        if self.completed_sentences_count >= self.max_sentences:
            self.reference_text = "TEST_FINISHED"
            self.reference_words = []
            return

        # 循環利用
        if self.current_sentence_index >= self.total_sentence:
            self.current_sentence_index = 0

        self.reference_text = self.phrases[self.current_sentence_index]
        self.reference_words = self.reference_text.split()
        
        self.current_sentence_index += 1
        
        # フレーズ開始時刻を記録
        self.phrase_start_time = time.time()
        self.backspace_count = 0 

    def getReferenceText(self) -> str:
        return self.reference_text

    def start(self):
        """全体計測開始（最初の1文目ロード時に呼ばれる想定）"""
        self.start_time = time.time()
        self.miss_counts = defaultdict(int)

    def increment_backspace(self):
        self.backspace_count += 1

    def check_input(self, input_words: list[str]) -> dict:
        results = []
        all_correct_so_far = True
        
        for i, word in enumerate(input_words):
            is_correct = False
            if i < len(self.reference_words):
                target_word = self.reference_words[i]
                if word.lower() == target_word.lower():
                    is_correct = True
            if not is_correct:
                all_correct_so_far = False
            results.append({"word": word, "is_correct": is_correct})

        is_completed = all_correct_so_far and (len(input_words) == len(self.reference_words))

        # 完了時の処理
        if is_completed:
            self.save_log(input_words)
            self.completed_sentences_count += 1

        return {
            "results": results,
            "is_completed": is_completed,
            "is_all_finished": self.reference_text == "TEST_FINISHED"
        }

    def save_log(self, input_words):
        """ログをCSVに保存"""
        input_phrase = " ".join(input_words)
        end_time = time.time()
        completion_time = end_time - self.phrase_start_time
        
        # WPM計算
        char_count = len(input_phrase)
        wpm = (char_count / 5) / (completion_time / 60.0) if completion_time > 0 else 0
        
        # Error Rate (TER) 計算: (Levenshtein距離 / 正解長)
        dist = self._levenshtein_distance(self.reference_text, input_phrase)
        ref_len = len(self.reference_text)
        error_rate = dist / ref_len if ref_len > 0 else 0

        # ディレクトリ作成
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # ファイル名 (被験者ごとに分ける場合)
        filename = f"logs/log_{self.participant_id}.csv"
        
        # ヘッダー書き込みチェック
        file_exists = os.path.isfile(filename)
        
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Timestamp", "ParticipantID", "Condition", "TrialID", 
                    "TargetPhrase", "InputPhrase", 
                    "CompletionTime", "WPM", "ErrorRate", "BackspaceCount"
                ])
            
            writer.writerow([
                datetime.now().isoformat(),
                self.participant_id,
                self.condition,
                self.completed_sentences_count + 1,
                self.reference_text,
                input_phrase,
                f"{completion_time:.3f}",
                f"{wpm:.2f}",
                f"{error_rate:.4f}",
                self.backspace_count
            ])
            print(f"[TypingTest] Log saved: Trial {self.completed_sentences_count + 1}, WPM={wpm:.2f}")

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