import re
import time
import difflib
from collections import defaultdict

class TypingTest:
    def __init__(self):
        self.phrases = []               # 読み込んだフレーズのリスト
        self.total_sentence = 0         # 全フレーズ数
        self.current_sentence_index = 0 # 現在のフレーズインデックス
        self.reference_text = "ReferenceText"
        self.reference_words = []       # 正解文を単語分割したリスト
        
        # 計測用
        self.start_time = 0.0
        self.end_time = 0.0
        self.miss_counts = defaultdict(int)

    def loadPhraseSet(self, dataset_path: str):
        """データセット読み込み"""
        try:
            with open(dataset_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # タグ等のクリーニング
            content_cleaned = re.sub(r'\[source:\s*\d+\]', '', content)
            
            self.phrases = [line.strip() for line in content_cleaned.split('\n') if line.strip()]
            self.total_sentence = len(self.phrases)
            self.current_sentence_index = 0
            
            print(f"[TypingTest] Loaded {self.total_sentence} phrases from {dataset_path}")
            
        except FileNotFoundError:
            print(f"[TypingTest] Error: File not found {dataset_path}")
            self.phrases = ["Error: Dataset not found"]
            self.total_sentence = 1

    def loadReferenceText(self):
        """次のフレーズをロード"""
        if not self.phrases:
            self.reference_text = "No phrases loaded."
            self.reference_words = []
            return

        if self.current_sentence_index >= self.total_sentence:
            self.current_sentence_index = 0

        self.reference_text = self.phrases[self.current_sentence_index]
        # 単語単位の判定のために分割しておく
        self.reference_words = self.reference_text.split()
        self.current_sentence_index += 1

    def getReferenceText(self) -> str:
        return self.reference_text

    def start(self):
        """計測開始"""
        self.start_time = time.time()
        self.miss_counts = defaultdict(int)

    # --- 新規追加: ロジックの中核 ---

    def check_input(self, input_words: list[str]) -> dict:
        """
        フロントエンドから送られてきた入力済み単語リストを評価する
        :param input_words: ユーザーが入力した単語のリスト
        :return: 判定結果を含む辞書
        """
        results = []
        all_correct_so_far = True
        
        # 各単語の正誤判定
        for i, word in enumerate(input_words):
            is_correct = False
            # 正解の単語数を超えて入力している場合はFalse
            if i < len(self.reference_words):
                target_word = self.reference_words[i]
                # 大文字小文字を区別せずに比較
                if word.lower() == target_word.lower():
                    is_correct = True
            
            if not is_correct:
                all_correct_so_far = False

            results.append({
                "word": word,
                "is_correct": is_correct
            })

        # 完了判定: 全ての単語が正解で、かつ単語数が一致しているか
        is_completed = all_correct_so_far and (len(input_words) == len(self.reference_words))

        return {
            "results": results,      # 各単語の判定結果リスト
            "is_completed": is_completed, # 全文完了したか
            "reference_words_count": len(self.reference_words) # フロント表示用
        }

    # --------------------------------

    def calcWPM(self, typed_text: str = None) -> int:
        """WPM計算"""
        current_time = time.time()
        duration_sec = current_time - self.start_time
        if duration_sec <= 0: return 0
        duration_min = duration_sec / 60.0
        
        text_len = len(typed_text) if typed_text is not None else len(self.reference_text)
        wpm = (text_len / 5) / duration_min
        return int(wpm)

    def calcErrorRate(self, typed_text: str) -> float:
        """簡易エラー率計算"""
        if not typed_text or not self.reference_text: return 0.0
        matcher = difflib.SequenceMatcher(None, self.reference_text, typed_text)
        return 1.0 - matcher.ratio()