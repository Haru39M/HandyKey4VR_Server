import kenlm
import os
import json
from collections import defaultdict
# jsonify と request を追加
from flask import Flask, render_template, request, jsonify
from word_predictor import WordPredictor
from typing_test import TypingTest

model_path = 'wiki_en_token.arpa.bin'
predictor = WordPredictor(model_path)

tester = TypingTest()
tester.loadPhraseSet('phrases2.txt')
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
                           js_reverse_map=json.dumps(predictor.REVERSE_QWERTY_MAP))

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

    predictor.set_text_input(input_word)
    # 3. ランク付け
    ranked_predictions = predictor.predict_top_words()
    predictions = ranked_predictions

    converted_index = predictor.current_index_sequence
    total_combinations = predictor.qwerty_combinations

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