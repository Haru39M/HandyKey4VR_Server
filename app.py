import kenlm
import os
import json
from collections import defaultdict
# jsonify と request を追加
from flask import Flask, render_template, request, jsonify

# ------------------------------------------------
# ユーザー提供のコード (変更なし)
# ------------------------------------------------
MODEL_BIN='wiki_en_token.arpa.bin'

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

REVERSE_QWERTY_MAP = {char: key for key, chars in QWERTY_MAP.items() for char in chars}

def text_to_qwerty_index(text):
    """単語をQWERTYキーボードの指のインデックスに変換する。"""
    if REVERSE_QWERTY_MAP:
        try:
            return "".join([REVERSE_QWERTY_MAP[char] for char in text.lower()])
        except KeyError:
            return None
    return None

def index_to_qwerty_words(index: str):
    """インデックスの連続から、考えられる全ての文字列の組み合わせを生成して返す。"""
    if not index: return []
    words = [""]
    for i in index:
        if i in QWERTY_MAP:
            letters = QWERTY_MAP[i]
            words = [prefix + char for prefix in words for char in letters]
        else:
            return []
    return words

def get_ranked_words(candidate_words, model):
    """
    単語候補のリストを受け取り、言語モデルでスコアリングして
    確率の高い順にソートしたリストを返す。
    """
    if not candidate_words:
        return []
    result = []
    for txt in candidate_words:
        prob = model.score(txt, bos=True, eos=True)
        result.append([prob, txt])
    sorted_result = sorted(result, reverse=True, key=lambda x: x[0])
    return [item[1] for item in sorted_result]

# ------------------------------------------------
# グローバル変数のロード (変更なし)
# ------------------------------------------------
if not os.path.exists(MODEL_BIN):
    raise Exception(f"モデルファイルが見つかりません: {MODEL_BIN}")
print("モデルを読み込んでいます...")
model = kenlm.LanguageModel(MODEL_BIN)
print("モデル読み込み完了！")

# ------------------------------------------------
# Flaskアプリケーション (ここから変更)
# ------------------------------------------------
app = Flask(__name__) # static_folder='static' が自動的に設定される

@app.route('/', methods=['GET'])
def index():
    """
    メインのHTMLページをレンダリングする。
    JSで使うための QWERTY_MAP をJSON文字列としてHTMLに埋め込む。
    """
    return render_template('index.html', 
                           js_reverse_map=json.dumps(REVERSE_QWERTY_MAP))

@app.route('/predict', methods=['POST'])
def predict():
    """
    予測リクエストを処理するJSON APIエンドポイント。
    """
    data = request.json
    input_word = data.get('word', '').strip()

    if not input_word:
        # エラーレスポンス
        return jsonify({"error": "入力がありません。"}), 400

    # 1. インデックスに変換
    converted_index = text_to_qwerty_index(input_word)
    
    if not converted_index:
        return jsonify({"error": f"単語「{input_word}」をインデックスに変換できませんでした。(QWERTYマップ外の文字？)"}), 400

    # 2. 候補生成
    candidate_words = index_to_qwerty_words(converted_index)
    total_combinations = len(candidate_words)

    if not candidate_words:
        return jsonify({"error": f"インデックス「{converted_index}」から候補を生成できませんでした。"}), 400

    # 3. ランク付け
    ranked_predictions = get_ranked_words(candidate_words, model)
    predictions = ranked_predictions[:10]

    # 4. 成功レスポンス (JSON)
    return jsonify({
        "predictions": predictions,
        "input_word": input_word,
        "converted_index": converted_index,
        "total_combinations": total_combinations
    })

# ------------------------------------------------
# アプリケーションの実行 (変更なし)
# ------------------------------------------------
if __name__ == '__main__':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0',port = 5000,debug=True)