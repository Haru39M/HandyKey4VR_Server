import kenlm
import os
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
from word_predictor import WordPredictor
from typing_test import TypingTest
from gesture_test import GestureTest 

# --- モデルとロジックの初期化 ---
model_path = 'wiki_en_token.arpa.bin'
_predictor = None

def get_predictor():
    global _predictor
    if _predictor is None:
        print("[App] Loading model...")
        _predictor = WordPredictor(model_path)
        print("[App] Model loaded.")
    return _predictor

# タイピングテスト用
tester = TypingTest()
tester.loadPhraseSet('phrases2.txt')

# ジェスチャーテスト用
gesture_tester = GestureTest('gestures/gestures.json')

app = Flask(__name__)

# =================================================
#  共通 / タイピングテスト関連
# =================================================

@app.route('/', methods=['GET'])
def index():
    predictor = get_predictor()
    return render_template('index.html', 
                           js_reverse_map=json.dumps(predictor.REVERSE_QWERTY_MAP))

@app.route('/predict', methods=['POST'])
def predict():
    predictor = get_predictor()
    data = request.json
    input_word = data.get('word', '').strip()

    if not input_word:
        predictor.clear()
        return jsonify({"predictions": [], "converted_index": "", "total_combinations": 0})

    predictor.set_text_input(input_word)
    ranked_predictions = predictor.predict_top_words_with_scores(limit=10,beam_width=10000)

    return jsonify({
        "predictions": ranked_predictions,
        "input_word": input_word,
        "converted_index": predictor.current_index_sequence,
        "total_combinations": predictor.qwerty_combinations
    })

@app.route('/test/start', methods=['POST'])
def start_test():
    data = request.json
    tester.configure_test(
        data.get('participant_id', 'test'),
        data.get('condition', 'default'),
        data.get('max_sentences', 5),
        data.get('handedness', 'R') # 利き手追加
    )
    tester.loadReferenceText()
    return jsonify({'reference_text': tester.getReferenceText()})

@app.route('/test/next', methods=['POST'])
def next_phrase():
    events = request.json.get('events', [])
    if events:
        tester.log_client_events(events)
    tester.loadReferenceText()
    return jsonify({'reference_text': tester.getReferenceText()})

@app.route('/test/check', methods=['POST'])
def check_input():
    data = request.json
    committed_words = data.get('committed_words', [])
    events = data.get('events', [])
    if events:
        tester.log_client_events(events)
    
    result = tester.check_input(committed_words)
    return jsonify(result)

@app.route('/test/backspace', methods=['POST'])
def notify_backspace():
    tester.increment_backspace()
    return jsonify({"status": "ok"})


# =================================================
#  ジェスチャーテスト関連
# =================================================

@app.route('/gesture', methods=['GET'])
def gesture_page():
    """ジェスチャーテスト画面"""
    return render_template('gesture.html')

@app.route('/gesture_images/<path:filename>')
def serve_gesture_image(filename):
    return send_from_directory('gestures/gesture_images', filename)

@app.route('/gesture/start', methods=['POST'])
def start_gesture_test():
    """ジェスチャーテスト開始"""
    data = request.json
    gesture_tester.configure_test(
        data.get('participant_id', 'test'),
        data.get('condition', 'default'),
        data.get('max_trials', 10),
        data.get('handedness', 'R') # 利き手追加
    )
    return jsonify({"status": "started"})

@app.route('/gesture/input', methods=['POST'])
def update_gesture_input():
    data = request.json
    if data:
        gesture_tester.update_input(data)
    return jsonify({"status": "updated"})

@app.route('/gesture/state', methods=['GET'])
def get_gesture_state():
    state = gesture_tester.check_state()
    return jsonify(state)


if __name__ == '__main__':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=5000, debug=True)