import kenlm
import os
import json
from flask import Flask, render_template, request, jsonify,send_from_directory
from word_predictor import WordPredictor
from typing_test import TypingTest
from gesture_test import GestureTest

app = Flask(__name__)

# --- 変更点: グローバルでの初期化をやめて、遅延ロード用の変数を定義 ---
model_path = 'wiki_en_token.arpa.bin'
_predictor = None  # 内部保持用変数

def get_predictor():
    """
    必要になったタイミングで初めてモデルをロードする関数
    """
    global _predictor
    if _predictor is None:
        print("[App] モデルのロードを開始します（初回アクセス）...")
        # ここで WordPredictor を初期化（ダウンロード処理も走る）
        _predictor = WordPredictor(model_path)
        print("[App] モデルのロードが完了しました。")
    return _predictor
# -------------------------------------------------------------

tester = TypingTest()
tester.loadPhraseSet('phrases2.txt')

gesture_tester = GestureTest('gestures/gestures.json')

@app.route('/', methods=['GET'])
def index():
    # ここで初めてロードが走る
    predictor = get_predictor()
    
    return render_template('index.html', 
                           js_reverse_map=json.dumps(predictor.REVERSE_QWERTY_MAP))

@app.route('/predict', methods=['POST'])
def predict():
    """予測API"""
    data = request.json
    input_word = data.get('word', '').strip()
    
    # ここでも取得関数経由でアクセス
    predictor = get_predictor()

    if not input_word:
        predictor.clear()
        return jsonify({"predictions": [], "converted_index": "", "total_combinations": 0})

    predictor.set_text_input(input_word)
    
    # 候補取得（スコア付き）
    ranked_predictions = predictor.predict_top_words_with_scores(limit=10)

    return jsonify({
        "predictions": ranked_predictions,
        "input_word": input_word,
        "converted_index": predictor.current_index_sequence,
        "total_combinations": predictor.qwerty_combinations
    })

# --- タイピングテスト & ロギング用API ---

@app.route('/test/start', methods=['POST'])
def start_test():
    """テスト開始設定"""
    data = request.json
    tester.configure_test(
        data.get('participant_id', 'test'),
        data.get('condition', 'default'),
        data.get('max_sentences', 5)
    )
    tester.loadReferenceText()
    return jsonify({'reference_text': tester.getReferenceText()})

@app.route('/test/next', methods=['POST'])
def next_phrase():
    """次のフレーズへ"""
    events = request.json.get('events', [])
    if events:
        tester.log_client_events(events)
        
    tester.loadReferenceText()
    return jsonify({'reference_text': tester.getReferenceText()})

@app.route('/test/check', methods=['POST'])
def check_input():
    """正誤判定 & ログ受信"""
    data = request.json
    committed_words = data.get('committed_words', [])
    
    events = data.get('events', [])
    if events:
        tester.log_client_events(events)
    
    result = tester.check_input(committed_words)
    return jsonify(result)

# =================================================
#  ジェスチャーテスト関連 (新規追加)
# =================================================

@app.route('/gesture', methods=['GET'])
def gesture_page():
    """ジェスチャーテスト画面"""
    return render_template('gesture.html')

@app.route('/gesture_images/<path:filename>')
def serve_gesture_image(filename):
    """ジェスチャー画像を配信する"""
    # gestures/gesture_images フォルダから配信
    return send_from_directory('gestures/gesture_images', filename)

@app.route('/gesture/start', methods=['POST'])
def start_gesture_test():
    """ジェスチャーテスト開始"""
    data = request.json
    gesture_tester.configure_test(
        data.get('participant_id', 'test'),
        data.get('condition', 'default'),
        data.get('max_trials', 10)
    )
    return jsonify({"status": "started"})

@app.route('/gesture/input', methods=['POST'])
def update_gesture_input():
    """
    デバイス(Bridge)からの入力データ受信
    期待フォーマット: {"T": "OPEN", "I": "CLOSE", ...}
    """
    data = request.json
    if data:
        gesture_tester.update_input(data)
    return jsonify({"status": "updated"})

@app.route('/gesture/state', methods=['GET'])
def get_gesture_state():
    """現在のステータス（判定結果含む）を取得"""
    state = gesture_tester.check_state()
    return jsonify(state)

if __name__ == '__main__':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=5000, debug=True)