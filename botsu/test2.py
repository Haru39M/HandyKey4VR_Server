import kenlm
import os

QWERTY_MAP = {
    '0': "tgb",# 左手人差し指
    '1': "yhn",# 右手人差し指
    '2': "rfv",# 左手人差し指
    '3': "ujm",# 右手人差し指
    '4': "edc",# 左手中指
    '5': "ik",# 右手中指 (「,」も担当範囲)
    '6': "wsx",# 左手薬指
    '7': "ol",# 右手薬指 (「.」も担当範囲)
    '8': "qaz",# 左手小指
    '9': "p",# 右手小指 (記号も担当範囲)
}

# 与えられたテキストをQWERTYインデックスに変換
def text_to_qwerty_index(text):
    """
    単語をQWERTYキーボードの指のインデックス（0〜7）に変換する。
    例: "hello" -> "12555"
    """
    index = []
    # 入力テキストを小文字に統一してループ
    for char in text.lower():
        # マップのキーと値（担当文字）でループ
        for finger_index, letters in QWERTY_MAP.items():
            if char in letters:
                index.append(finger_index)
                break # 文字が見つかったら内側のループを抜ける

    return "".join(index)

# 与えられたQWERTYインデックスから全通りの文字列を生成
def index_to_qwerty_words(index: str):
    """
    QWERTYキーボードの指のインデックス（0〜7）の連続から、
    考えられる全ての文字列の組み合わせを生成して返す。
    """
    # 候補となる単語を格納するリスト
    words = [""]

    for i in index:
        # QWERTY_MAPにインデックスが存在するかチェック
        if i in QWERTY_MAP:
            letters = QWERTY_MAP[i]
            # これまでの全文字列(words)と新しい文字(letters)を組み合わせて
            # 新しいリストを作成
            words = [prefix + char for prefix in words for char in letters]

    return words

def find_qwerty_typos(word: str) -> list[str]:
    """
    単語をインデックスに変換し、そこから生成される全文字列（タイポ候補）を返す。
    """
    # 1. 単語をQWERTYインデックスに変換
    qwerty_index = text_to_qwerty_index(word)
    print(f"入力単語 '{word}' はインデックス '{qwerty_index}' に変換されました。")

    # 2. インデックスから全通りの文字列を生成
    combinations = index_to_qwerty_words(qwerty_index)

    return combinations

def count_qwerty_combinations(word: str) -> int:
    """
    単語と同じ指の運びで生成可能な文字列の総数を計算して返す。
    """
    # 1. 単語をQWERTYインデックスに変換する
    qwerty_index = text_to_qwerty_index(word)

    # 2. インデックスが空の場合（例：入力が"!!"など）は0通りとする
    if not qwerty_index:
        return 0

    # 3. 総数を計算する
    total_combinations = 1
    for index_char in qwerty_index:
        # 各インデックスに対応する文字の数を掛け合わせる
        num_choices = len(QWERTY_MAP[index_char])
        total_combinations *= num_choices

    return total_combinations

if __name__ == "__main__":

    MODEL_BIN='wiki_en_token.arpa.bin'
    # MODEL_BIN='/content/drive/MyDrive/wiki_en_pos.arpa.bin'

    if not os.path.exists(MODEL_BIN):
        raise Exception("model file not found: {}".format(MODEL_BIN))
    print("loading model...")
    model = kenlm.LanguageModel(MODEL_BIN)
    print("done!")

    while True:
        input_word = input("input word >>")
        possible_typos = find_qwerty_typos(input_word)
        test = [
            "now",
            "nox"
        ]
        result = []
        for txt in possible_typos:
            # sentence = " ".join(txt.strip())
            sentence = txt
            prob = model.score(sentence, bos=True, eos=True)
            perplexity = model.perplexity(sentence)
            result.append([perplexity, prob, txt])
            # print(sentence,perplexity, prob, txt)
        sorted_result = sorted(result, reverse=True, key=lambda x: x[1])
        final_words = [item[2] for item in sorted_result]
        
        max_count = count_qwerty_combinations(input_word)
        word_order = final_words.index(input_word)
        print(final_words[:10])
        print(f"{input_word}:{word_order+1}/{max_count}")