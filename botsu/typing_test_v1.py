import re
import time
import difflib
from collections import defaultdict

"""
データセットを読み込む．
1行ロードし，1単語ずつ順番にgetする
WPMを計算する
エラー率を計算する
アルファベット(a~z)ごとのミス回数
"""
class TypingTest:
    def __init__(self):
        self.phrases = []               # 読み込んだフレーズのリスト
        self.total_sentence = 0         # 全フレーズ数
        self.current_sentence_index = 0 # 現在のフレーズインデックス
        self.reference_text = "ReferenceText"
        
        # 計測用
        self.start_time = 0.0
        self.end_time = 0.0
        self.miss_counts = defaultdict(int) # 文字ごとのミス回数 ('a': 1, 'b': 0...)

    def loadPhraseSet(self, dataset_path: str):
        """
        phrases2.txt等を読み込み、タグを除去してリスト化する
        """
        try:
            with open(dataset_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # のタグを削除
            content_cleaned = re.sub(r'\\', '', content)
            
            # 行ごとに分割し、空白除去。空行は除外。
            self.phrases = [line.strip() for line in content_cleaned.split('\n') if line.strip()]
            self.total_sentence = len(self.phrases)
            self.current_sentence_index = 0
            
            print(f"[TypingTest] Loaded {self.total_sentence} phrases from {dataset_path}")
            
        except FileNotFoundError:
            print(f"[TypingTest] Error: File not found {dataset_path}")
            self.phrases = ["Error: Dataset not found"]
            self.total_sentence = 1

    def loadReferenceText(self):
        """
        次のフレーズをロードしてセットする
        """
        if not self.phrases:
            self.reference_text = "No phrases loaded."
            return

        # インデックスが範囲外なら最初に戻る（ループ）
        if self.current_sentence_index >= self.total_sentence:
            self.current_sentence_index = 0

        self.reference_text = self.phrases[self.current_sentence_index]
        self.current_sentence_index += 1

    def setReferenceText(self, reference_text: str):
        self.reference_text = reference_text
    
    def getReferenceText(self) -> str:
        return self.reference_text

    def start(self):
        """
        タイピング開始時刻を記録する
        """
        self.start_time = time.time()
        self.miss_counts = defaultdict(int) # ミスカウントをリセット

    def calcWPM(self, typed_text: str = None) -> int:
        """
        WPM (Words Per Minute) を計算する
        式: (文字数 / 5) / 分
        """
        current_time = time.time()
        duration_sec = current_time - self.start_time
        
        # 0除算防止
        if duration_sec <= 0:
            return 0
        
        duration_min = duration_sec / 60.0
        
        # 入力テキストが渡されていない場合は参照テキストの長さを使用（完了したと仮定）
        text_len = len(typed_text) if typed_text is not None else len(self.reference_text)
        
        # 一般的なWPM計算: 5文字を1単語とみなす
        wpm = (text_len / 5) / duration_min
        return int(wpm)

    def calcErrorRate(self, typed_text: str) -> float:
        """
        エラー率を計算し、文字ごとのミスもカウントする。
        Error Rate = (編集距離) / (正解文の長さ)
        """
        if not typed_text or not self.reference_text:
            return 0.0

        # 文字ごとの差分を解析してミスカウントを更新
        self._analyze_misses(self.reference_text, typed_text)

        # Levenshtein距離に似た比率計算 (difflibを使用)
        # SequenceMatcher.ratio() は 0~1 の類似度を返す。1.0が完全一致。
        # ここでは簡易的に (1 - ratio) をエラー率指標とするか、
        # より厳密には (変更が必要な文字数 / 元の長さ) を計算する。
        
        matcher = difflib.SequenceMatcher(None, self.reference_text, typed_text)
        distance = self._levenshtein_distance(self.reference_text, typed_text)
        
        # エラー率 = 編集距離 / (正解文の長さ)
        ref_len = len(self.reference_text)
        if ref_len == 0: return 0.0
        
        error_rate = distance / ref_len
        return error_rate

    def _analyze_misses(self, ref: str, typed: str):
        """
        difflibを使って文字単位の差異を検出し、miss_countsに加算する
        """
        # ndiff は差分をジェネレータで返す
        # '- ': refにあってtypedにない（削除/ミス）
        # '+ ': typedにあってrefにない（挿入）
        # '  ': 一致
        diff = difflib.ndiff(ref, typed)
        
        for d in diff:
            code = d[0]
            char = d[2:].lower() # 大文字小文字は区別せずカウント（要件に合わせて調整）
            
            if code == '-':
                # 正解にある文字が打たれなかった（または間違えた）場合
                if 'a' <= char <= 'z':
                    self.miss_counts[char] += 1

    def _levenshtein_distance(self, s1, s2):
        """
        標準ライブラリのみで編集距離を計算する簡易実装
        """
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

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

    def getMissCounts(self):
        """
        ミスした文字のカウント辞書を返す
        """
        return dict(self.miss_counts)