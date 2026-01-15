import kenlm
import os
import subprocess

class WordPredictor:
    def __init__(self, model_path='wiki_en_token.arpa.bin'):
        """
        初期化
        :param model_path: KenLMのモデルファイルパス
        """
        self.qwerty_combinations = 0
        if not os.path.exists(model_path):
            print(f"[Predictor] モデルが見つかりません: {model_path}")
            print("[Predictor] get_model.sh を実行してモデルを取得します...")
            try:
                # シェルスクリプトを実行してモデルをダウンロード
                subprocess.run(["sh", "get_model.sh"], check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"モデルのダウンロードに失敗しました。終了コード: {e.returncode}")
            except Exception as e:
                raise RuntimeError(f"予期せぬエラーが発生しました: {e}")

            # ダウンロード後に再確認
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"ダウンロード処理は完了しましたが、ファイルが見つかりません: {model_path}")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"モデルファイルが見つかりません: {model_path}")
        
        print(f"[Predictor] Loading model: {model_path} ...")
        self.model = kenlm.LanguageModel(model_path)
        print("[Predictor] Model loaded.")

        # 現在入力中のインデックス列を保持するバッファ
        self.current_index_sequence = ""

        # マッピング定義
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
        if 0 <= index_val <= 7: # キーマップに合わせて適宜調整
             # 注意: 上記QWERTY_MAPのキーは文字列の '0'~'9' ですが、
             # handle_index_inputの引数がintの場合の変換はシステム全体で整合性をとってください。
             # ここでは簡易的にstr変換して追加します
            self.current_index_sequence += str(index_val)
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
    #  予測ロジック
    # =========================================================

    def predict_top_words(self, limit=6, beam_width=10000):
        """
        VRChat用など、文字列リストだけ欲しい場合に使用
        """
        if not self.current_index_sequence:
            return []
        top_candidates = self._beam_search(self.current_index_sequence, beam_width)
        return [word for score, word in top_candidates[:limit]]

    def predict_top_words_with_scores(self, limit=6, beam_width=100000):
        """
        WEB UI用。スコア情報も含めて返す。
        :return: [{"word": str, "score": float}, ...]
        """
        if not self.current_index_sequence:
            return []
        
        top_candidates = self._beam_search(self.current_index_sequence, beam_width)
        
        # UI表示用に整形して返す
        return [{"word": word, "score": score} for score, word in top_candidates[:limit]]

    def _beam_search(self, index_seq, width):
        """
        ビームサーチ本体
        :return: (score, word) のリスト (スコア降順)
        """
        current_hypotheses = [(0.0, "")]

        for i_char in index_seq:
            # マッピングになければスキップ
            if i_char not in self.QWERTY_MAP:
                continue # あるいは return []

            possible_chars = self.QWERTY_MAP[i_char]
            next_hypotheses = []

            for score, word in current_hypotheses:
                for char in possible_chars:
                    new_word = word + char
                    new_score = self.model.score(new_word)
                    next_hypotheses.append((new_score, new_word))
            
            # ソートして上位width件を残す
            next_hypotheses.sort(key=lambda x: x[0], reverse=True)
            current_hypotheses = next_hypotheses[:width]

        return current_hypotheses

    def count_qwerty_combinations(self, index_seq: str) -> int:
        total_combinations = 1
        for index_char in index_seq:
            if index_char in self.QWERTY_MAP:
                total_combinations *= len(self.QWERTY_MAP[index_char])
        return total_combinations