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
    """予測API (Web UI用)"""
    data = request.json
    input_word = data.get('word', '').strip()

    if not input_word:
        predictor.clear()
        return jsonify({"predictions": [], "converted_index": "", "total_combinations": 0})

    predictor.set_text_input(input_word)
    
    # ★変更点: スコア付きのメソッドを呼ぶ
    ranked_predictions = predictor.predict_top_words_with_scores(limit=10)

    return jsonify({
        "predictions": ranked_predictions, # [{"word":.., "score":..}, ...]
        "input_word": input_word,
        "converted_index": predictor.current_index_sequence,
        "total_combinations": predictor.qwerty_combinations
    })

# --- タイピングテスト用API ---

@app.route('/test/start', methods=['POST'])
def start_test():
    """テスト開始（パラメータ設定含む）"""
    data = request.json
    participant_id = data.get('participant_id', 'test_user')
    condition = data.get('condition', 'default')
    max_sentences = data.get('max_sentences', 5)
    
    tester.configure_test(participant_id, condition, max_sentences)
    tester.loadReferenceText()
    
    return jsonify({'reference_text': tester.getReferenceText()})

@app.route('/test/next', methods=['POST'])
def next_phrase():
    """次のフレーズへ"""
    tester.loadReferenceText()
    return jsonify({'reference_text': tester.getReferenceText()})

@app.route('/test/check', methods=['POST'])
def check_input():
    data = request.json
    committed_words = data.get('committed_words', [])
    result = tester.check_input(committed_words)
    return jsonify(result)

@app.route('/test/backspace', methods=['POST'])
def notify_backspace():
    """バックスペースログ用"""
    tester.increment_backspace()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=5000, debug=True)