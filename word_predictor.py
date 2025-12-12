import kenlm
import os
import json

class WordPredictor:
    def __init__(self, model_path='wiki_en_token.arpa.bin'):
        """
        初期化
        :param model_path: KenLMのモデルファイルパス
        """
        # ビームサーチ導入により、組み合わせ数の上限チェックは不要化
        # self.max_candidates_num = 50000000 
        self.qwerty_combinations = 0

        if not os.path.exists(model_path):
            # モデルがない場合のダミー処理(テスト実行用)回避のため、実際はエラーかパス確認が必要
            # ここでは例外を投げる元の動作を維持
            raise FileNotFoundError(f"モデルファイルが見つかりません: {model_path}")
        
        print(f"[Predictor] Loading model: {model_path} ...")
        self.model = kenlm.LanguageModel(model_path)
        print("[Predictor] Model loaded.")

        # 現在入力中のインデックス列を保持するバッファ
        self.current_index_sequence = ""

        # マッピング定義
        # self.QWERTY_MAP = {
        #     '0': "tgbrfv",
        #     '1': "yhnujm",
        #     '2': "edc",
        #     '3': "ik",
        #     '4': "wsx",
        #     '5': "ol",
        #     '6': "qaz",
        #     '7': "p",
        # }
        self.QWERTY_MAP = {
            '1': "qaz",# 左小指
            '2': "wsx",# 左薬指
            '3': "edc",# 左中指
            '4': "tgbrfv",# 左人差し指
            '7': "yhnujm",# 右人差し指
            '8': "ik",# 右中指
            '9': "ol",# 右薬指
            '0': "p",# 右小指
        }
        # 逆引きマップ
        self.REVERSE_QWERTY_MAP = {char: key for key, chars in self.QWERTY_MAP.items() for char in chars}

    # =========================================================
    #  入力処理メソッド
    # =========================================================

    def handle_index_input(self, index_val: int):
        if 0 <= index_val <= 7:
            self.current_index_sequence += str(index_val)
            # 組み合わせ数は参考用として残すが、判定には使わない
            self.qwerty_combinations = self.count_qwerty_combinations(self.current_index_sequence)
            print(f"[Predictor] updated index seq: {self.current_index_sequence}")
        else:
            print(f"[Predictor] Invalid index input: {index_val}")

    def handle_backspace(self):
        if len(self.current_index_sequence) > 0:
            self.current_index_sequence = self.current_index_sequence[:-1]
            self.qwerty_combinations = self.count_qwerty_combinations(self.current_index_sequence)

    def clear(self):
        self.current_index_sequence = ""
        self.qwerty_combinations = 0

    def set_text_input(self, text: str):
        indices = []
        for char in text.lower():
            if char in self.REVERSE_QWERTY_MAP:
                indices.append(self.REVERSE_QWERTY_MAP[char])
        self.current_index_sequence = "".join(indices)
        self.qwerty_combinations = self.count_qwerty_combinations(self.current_index_sequence)

    def get_current_sequence(self):
        return self.current_index_sequence

    # =========================================================
    #  予測ロジック (Beam Searchに変更)
    # =========================================================

    def predict_top_words(self, limit=6, beam_width=10000):
        """
        ビームサーチを用いて、現在のインデックス列から尤もらしい単語候補を探索する
        """
        print(f"[Predictor] predicting with Beam Search (K={beam_width})...")
        
        if not self.current_index_sequence:
            return []

        # ビームサーチの実行
        top_candidates = self._beam_search(self.current_index_sequence, beam_width)
        
        print(f"[Predictor] predict DONE")
        # 上位limit件の単語のみを返す
        return [word for score, word in top_candidates[:limit]]

    def _beam_search(self, index_seq, width):
        """
        ビームサーチ本体
        :return: (score, word) のリスト (スコア降順)
        """
        # 初期状態: (スコア, 単語文字列)
        # KenLMのscoreは対数確率(log10)なので、初期値は0.0
        current_hypotheses = [(0.0, "")]

        # 入力された数字列を1つずつ処理
        for i_char in index_seq:
            next_hypotheses = []
            
            # マッピングが存在しない文字が来た場合はスキップ(あるいは中断)
            if i_char not in self.QWERTY_MAP:
                return []

            possible_chars = self.QWERTY_MAP[i_char] # 例: "tgbrfv"

            # 現在の候補(ビーム幅分)に対して、次の文字を総当たりで付与
            for score, word in current_hypotheses:
                for char in possible_chars:
                    new_word = word + char
                    # KenLMでスコアリング (ここでは簡易的に毎回全文スコア計算)
                    # 文字レベルモデルなら eos=False の方が途中経過として自然だが、
                    # 最終的な単語としての尤度を見るためデフォルト設定で計算して比較する
                    new_score = self.model.score(new_word)
                    
                    next_hypotheses.append((new_score, new_word))
            
            # スコアが高い順にソートして、上位 width 件だけを残す (枝刈り)
            next_hypotheses.sort(key=lambda x: x[0], reverse=True)
            current_hypotheses = next_hypotheses[:width]

        return current_hypotheses

    def count_qwerty_combinations(self, index_seq: str) -> int:
        """組み合わせ総数計算（デバッグ・統計用）"""
        total_combinations = 1
        for index_char in index_seq:
            if index_char in self.QWERTY_MAP:
                total_combinations *= len(self.QWERTY_MAP[index_char])
        return total_combinations

# 単体テスト用
if __name__ == "__main__":
    try:
        # モデルパスは環境に合わせて変更してください
        predictor = WordPredictor('wiki_en_token.arpa.bin') 
        
        # テスト: 長い単語 "circumstances" (13文字)
        # 従来の全探索では 6^13 ≒ 130億通りでメモリ溢れ・タイムアウトするケース
        target_word = "circumstances"
        print(f"\n--- Test: Long Word Input '{target_word}' ---")
        
        predictor.set_text_input(target_word)
        seq = predictor.get_current_sequence()
        comb = predictor.count_qwerty_combinations(seq)
        
        print(f"Index Sequence: {seq}")
        print(f"Theoretical Combinations: {comb:,}") # 巨大な数字になる
        
        # ビームサーチなら一瞬で終わるはず
        import time
        start = time.time()
        candidates = predictor.predict_top_words(limit=10)
        elapsed = time.time() - start
        
        print(f"Time: {elapsed:.4f} sec")
        print(f"Candidates: {candidates}")

    except Exception as e:
        print(e)