import kenlm
import os
import json
from flask import Flask, render_template, request, jsonify
from word_predictor import WordPredictor
from typing_test import TypingTest

# モデルとロジックの初期化
model_path = 'wiki_en_token.arpa.bin'
predictor = WordPredictor(model_path)

tester = TypingTest()
tester.loadPhraseSet('phrases2.txt')

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', 
                           js_reverse_map=json.dumps(predictor.REVERSE_QWERTY_MAP))

@app.route('/predict', methods=['POST'])
def predict():
    """予測API"""
    data = request.json
    input_word = data.get('word', '').strip()

    if not input_word:
        predictor.clear()
        return jsonify({
            "predictions": [],
            "input_word": "",
            "converted_index": "",
            "total_combinations": 0
        })

    predictor.set_text_input(input_word)
    ranked_predictions = predictor.predict_top_words()

    return jsonify({
        "predictions": ranked_predictions,
        "input_word": input_word,
        "converted_index": predictor.current_index_sequence,
        "total_combinations": predictor.qwerty_combinations
    })

# --- タイピングテスト用API ---

@app.route('/test/start', methods=['POST'])
def start_test():
    """テスト開始"""
    tester.current_sentence_index = 0
    tester.loadReferenceText()
    tester.start()
    return jsonify({'reference_text': tester.getReferenceText()})

@app.route('/test/next', methods=['POST'])
def next_phrase():
    """次のフレーズへ"""
    tester.loadReferenceText()
    tester.start() 
    return jsonify({'reference_text': tester.getReferenceText()})

@app.route('/test/check', methods=['POST'])
def check_input():
    """
    入力済み単語リストを受け取り、正誤判定と完了状態を返す
    ロジックは全てバックエンド(TypingTest)が担う
    """
    data = request.json
    # フロントエンドから送られてきた入力済み単語のリスト
    committed_words = data.get('committed_words', [])
    
    # TypingTestクラスで判定
    result = tester.check_input(committed_words)
    
    # 結果を返す
    return jsonify(result)

if __name__ == '__main__':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=5000, debug=True)