import kenlm
import os
import json
import csv
import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from word_predictor import WordPredictor
from typing_test import TypingTest
from gesture_test import GestureTest 
# 新規インポート
from nasa_tlx import nasa_tlx_bp

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

# =================================================
#  【修正】パス設定 (app.pyより移植)
# =================================================
# app.py のあるディレクトリを基準にする
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GESTURES_PATH = os.path.join(BASE_DIR, 'gestures', 'gestures.json')
# 画像ディレクトリも絶対パスで定義
IMAGES_DIR = os.path.join(BASE_DIR, 'gestures', 'gesture_images')
LOGS_DIR = os.path.join(BASE_DIR, 'logs') # ログ保存用

# ログディレクトリがなければ作成
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

print(f"[App] Initializing GestureTest with path: {GESTURES_PATH}")

# ファイル存在チェック
if not os.path.exists(GESTURES_PATH):
    print(f"[App] CRITICAL WARNING: gestures.json NOT FOUND at {GESTURES_PATH}")

if not os.path.exists(IMAGES_DIR):
    print(f"[App] CRITICAL WARNING: Images directory NOT FOUND at {IMAGES_DIR}")

# タイピングテスト用
tester = TypingTest()
# phrases2.txtが存在しない場合のエラー回避
try:
    tester.loadPhraseSet('phrases2.txt')
except Exception as e:
    print(f"[App] Warning: phrases2.txt load failed: {e}")

# ジェスチャーテスト用
gesture_tester = GestureTest(GESTURES_PATH)

app = Flask(__name__)

# ★設定: ログフォルダをapp.configに保存し、Blueprintから参照可能にする
app.config['LOGS_FOLDER'] = LOGS_DIR

# ★登録: NASA-TLX Blueprint
app.register_blueprint(nasa_tlx_bp)

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

@app.route('/log', methods=['POST'])
def log_event():
    data = request.json
    tester.log_event(data)
    return jsonify({'status': 'ok'})

@app.route('/complete', methods=['POST'])
def complete_trial():
    data = request.json
    result = tester.complete_trial(data)
    return jsonify(result)

@app.route('/test/start', methods=['POST'])
def start_test():
    data = request.json
    tester.configure_test(
        data.get('participant_id', 'test'),
        data.get('condition', 'default'),
        data.get('max_sentences', 5),
        data.get('handedness', 'R')
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


# =================================================
#  ジェスチャーテスト関連
# =================================================

@app.route('/gesture', methods=['GET'])
def gesture_page():
    return render_template('gesture.html')

@app.route('/gesture_images/<path:filename>')
def serve_gesture_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/gesture/start', methods=['POST'])
def start_gesture_test():
    data = request.json
    gesture_tester.configure_test(
        data.get('participant_id', 'test'),
        data.get('condition', 'default'),
        data.get('max_trials', 10),
        data.get('handedness', 'R')
    )
    return jsonify({"status": "started"})

@app.route('/gesture/input', methods=['POST'])
def update_gesture_input():
    try:
        data = request.json
        if data:
            gesture_tester.update_input(data)
        return jsonify({"status": "updated"})
    except Exception as e:
        print(f"[App] Error in update_gesture_input: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/gesture/state', methods=['GET'])
def get_gesture_state():
    state = gesture_tester.check_state()
    return jsonify(state)

@app.route('/gesture/log', methods=['POST'])
def gesture_log():
    try:
        events = request.json
        if events:
            gesture_tester.log_client_events(events)
        return jsonify({"status": "logged"})
    except Exception as e:
        print(f"Log Error: {e}")
        return jsonify({"status": "error"}), 500


if __name__ == '__main__':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=5000, debug=True)