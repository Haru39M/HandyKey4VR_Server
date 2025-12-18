import kenlm
import os
import json
from collections import defaultdict

# --- 基本設定とQWERTYマップ (変更なし) ---
MODEL_BIN='wiki_en_token.arpa.bin'

# QWERTY_MAP = {
#     '0': "tgb",
#     '1': "yhn",
#     '2': "rfv",
#     '3': "ujm",
#     '4': "edc",
#     '5': "ik",
#     '6': "wsx",
#     '7': "ol",
#     '8': "qaz",
#     '9': "p",
# }

# 人差し指に2列持たせる場合(少し精度と速度が落ちる)
QWERTY_MAP = {
    '0': "tgbrfv",
    '1': "yhnujm",
    '2': "edc",
    '3': "ik",
    '4': "wsx",
    '5': "ol",
    '6': "qaz",
    '7': "p",
}

# 逆引きマップを事前に作成しておくと、変換処理が高速になります
try:
    REVERSE_QWERTY_MAP = {char: key for key, chars in QWERTY_MAP.items() for char in chars}
except NameError:
    # 互換性のためのフォールバック
    REVERSE_QWERTY_MAP = {}

# --- 既存のヘルパー関数 (一部修正) ---

def text_to_qwerty_index(text):
    """単語をQWERTYキーボードの指のインデックスに変換する。"""
    # 事前に計算した逆引きマップを使用する方が効率的
    if REVERSE_QWERTY_MAP:
        try:
            return "".join([REVERSE_QWERTY_MAP[char] for char in text.lower()])
        except KeyError as e:
            # マップにない文字が含まれていた場合
            # print(f"警告: 文字 '{e.args[0]}' はQWERTY_MAPに定義されていません。")
            return None
    
    # 逆引きマップがない場合の元のロジック
    index = []
    for char in text.lower():
        found = False
        for finger_index, letters in QWERTY_MAP.items():
            if char in letters:
                index.append(finger_index)
                found = True
                break
        if not found:
            # print(f"警告: 文字 '{char}' はQWERTY_MAPに定義されていません。")
            return None
    return "".join(index)

def index_to_qwerty_words(index: str):
    """インデックスの連続から、考えられる全ての文字列の組み合わせを生成して返す。"""
    if not index: return []
    words = [""]
    for i in index:
        if i in QWERTY_MAP:
            letters = QWERTY_MAP[i]
            words = [prefix + char for prefix in words for char in letters]
    return words

def find_qwerty_typos(word: str) -> list[str]:
    """単語から生成される全文字列（タイポ候補）を返す。"""
    qwerty_index = text_to_qwerty_index(word)
    if not qwerty_index: return []
    # print(f"入力単語 '{word}' はインデックス '{qwerty_index}' に変換されました。")
    return index_to_qwerty_words(qwerty_index)

def count_qwerty_combinations(word: str) -> int:
    """単語と同じ指の運びで生成可能な文字列の総数を計算して返す。"""
    qwerty_index = text_to_qwerty_index(word)
    if not qwerty_index: return 0
    total_combinations = 1
    for index_char in qwerty_index:
        total_combinations *= len(QWERTY_MAP[index_char])
    return total_combinations

# --- 新しく追加・整理した機能 ---

def load_words_from_json(filename="words.json"):
    """words.jsonファイルを読み込み、単語のセットを返す"""
    if not os.path.exists(filename):
        print(f"エラー: {filename} が見つかりません。")
        return None
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # 重複を除き、検索を高速化するためにセット(set)で返す
    return set(data.get("words", []))

def get_ranked_words(candidate_words, model):
    """
    単語候補のリストを受け取り、言語モデルでスコアリングして
    確率の高い順にソートしたリストを返す。
    """
    if not candidate_words:
        return []
    
    result = []
    for txt in candidate_words:
        # kenlm.model.scoreは対数確率を返すため、値が大きいほど確率が高い
        prob = model.score(txt, bos=True, eos=True)
        result.append([prob, txt])
    
    # 確率(prob)の降順でソート
    sorted_result = sorted(result, reverse=True, key=lambda x: x[0])
    return [item[1] for item in sorted_result]

def manual_mode(model):
    """ユーザーが手動で単語を入力し、変換候補をテストするモード"""
    print("\n--- 手動テストモード ---")
    print("単語を入力してください ('exit'でメニューに戻ります)")
    while True:
        input_word = input("input word >> ")
        if input_word.lower() == 'exit':
            break
        if not input_word:
            continue

        # 1. 全てのタイポ候補を生成する
        possible_typos = find_qwerty_typos(input_word)
        if not possible_typos:
            print(f"'{input_word}' に対応するキーが見つかりませんでした。")
            continue

        # 2. 候補をランク付けする
        final_words = get_ranked_words(possible_typos, model)
        
        # 3. 結果を表示する
        try:
            max_count = len(possible_typos)
            word_order = final_words.index(input_word)
            print("--- 予測結果 (上位10件) ---")
            print(final_words[:10])
            print("-" * 20)
            print(f"結果: '{input_word}' は {word_order + 1}番目 / {max_count}件中 です。")
            print("-" * 20)
        except ValueError:
            print(f"エラー: 予測候補に '{input_word}' が見つかりませんでした。")

def batch_test_mode(model, all_words):
    """words.jsonを読み込み、リスト内の全単語の正解率をテストするモード"""
    print("\n--- words.json一括テストモード ---")
    if not all_words:
        print("テスト対象の単語リストが空です。")
        return

    word_order_stats = defaultdict(int)
    total_words = len(all_words)
    processed_count = 0

    for target_word in all_words:
        processed_count += 1
        # 1. テスト対象単語のインデックスを取得
        qwerty_index = text_to_qwerty_index(target_word)
        if not qwerty_index:
            continue

        # 2. 辞書の中から、同じインデックスになりうる単語のみを候補として抽出
        # (find_qwerty_typosで全生成するより遥かに高速)
        candidate_words = [
            word for word in all_words 
            if text_to_qwerty_index(word) == qwerty_index
        ]
        
        # 3. 候補をランク付け
        final_words = get_ranked_words(candidate_words, model)

        # 4. 順位を記録
        try:
            rank = final_words.index(target_word)
            word_order_stats[rank] += 1
        except ValueError:
            # ランク付け候補の中に元の単語が含まれないケース（通常は発生しない）
            word_order_stats[-1] += 1 # エラーとしてカウント

        # 進捗表示
        if processed_count % 100 == 0:
            print(f"進捗: {processed_count} / {total_words}")
            
    # 5. 最終結果を集計して表示
    print("\n--- テスト結果 ---")
    total_tested = sum(word_order_stats.values())
    print(f"テスト単語数: {total_tested}")

    if not total_tested: return

    for i in range(max(word_order_stats.keys()) + 1):
        count = word_order_stats.get(i, 0)
        if count > 0:
            percentage = (count / total_tested) * 100
            print(f"{i + 1}位: {count}回 ({percentage:.2f}%)")
    
    if -1 in word_order_stats:
        print(f"エラー（候補に元単語なし）: {word_order_stats[-1]}回")

    # TOP N のヒット率
    top1_hits = word_order_stats.get(0, 0)
    top3_hits = sum(word_order_stats.get(i, 0) for i in range(3))
    print("-" * 20)
    print(f"Top 1 Hit Rate: {(top1_hits / total_tested) * 100:.2f}%")
    print(f"Top 3 Hit Rate: {(top3_hits / total_tested) * 100:.2f}%")
    print("-" * 20)


# --- メイン実行部 ---

if __name__ == "__main__":
    if not os.path.exists(MODEL_BIN):
        raise Exception(f"モデルファイルが見つかりません: {MODEL_BIN}")
    
    print("モデルを読み込んでいます...")
    model = kenlm.LanguageModel(MODEL_BIN)
    print("完了！")

    # メインループでモード選択
    while True:
        print("\n--- メインメニュー ---")
        print("1: 手動テストモード")
        print("2: words.json一括テストモード")
        print("q: 終了")
        choice = input("モードを選択してください >> ")

        if choice == '1':
            manual_mode(model)
        elif choice == '2':
            all_words = load_words_from_json("words.json")
            if all_words:
                batch_test_mode(model, all_words)
        elif choice.lower() == 'q':
            print("プログラムを終了します。")
            break
        else:
            print("無効な選択です。1, 2, または q を入力してください。")