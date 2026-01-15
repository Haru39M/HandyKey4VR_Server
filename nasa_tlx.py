import os
import csv
import datetime
from flask import Blueprint, render_template, request, current_app, jsonify, url_for

# Blueprintの作成
nasa_tlx_bp = Blueprint('nasa_tlx', __name__)

@nasa_tlx_bp.route('/nasa_tlx', methods=['GET'])
def page():
    """NASA-TLX アンケートページを表示"""
    tester_id = request.args.get('id', 'unknown')
    condition = request.args.get('con', 'unknown')
    task_type = request.args.get('task', 'unknown') # typing or gesture
    
    # 【修正】先頭のスラッシュを削除しました ('/nasa_tlx.html' -> 'nasa_tlx.html')
    return render_template('nasa_tlx.html', tester_id=tester_id, condition=condition, task_type=task_type)

@nasa_tlx_bp.route('/nasa_tlx/submit', methods=['POST'])
def submit():
    """NASA-TLXの結果を保存"""
    try:
        tester_id = request.form.get('tester_id')
        condition = request.form.get('condition')
        task_type = request.form.get('task_type', '')
        
        # 値の取得
        values = [
            request.form.get('q1'), # Mental
            request.form.get('q2'), # Physical
            request.form.get('q3'), # Temporal
            request.form.get('q4'), # Performance
            request.form.get('q5'), # Effort
            request.form.get('q6')  # Frustration
        ]
        
        # タイムスタンプ
        now_str = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        
        # CSVファイル名の生成
        filename = f'NASA-TLX_{tester_id}_{condition}_{task_type}_{now_str}.csv'
        
        # app.configから保存先パスを取得
        logs_dir = current_app.config.get('LOGS_FOLDER', 'logs')
        filepath = os.path.join(logs_dir, filename)
        
        # ヘッダー
        header = ['Mental', 'Physical', 'Temporal', 'Performance', 'Effort', 'Frustration']
        
        with open(filepath, 'w', newline='', encoding='utf_8_sig') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerow(values)
            
        print(f'[NASA-TLX] Saved: {filepath}')
        # 保存完了画面もスラッシュなしで指定
        return render_template('nasa_tlx.html', done=True, tester_id=tester_id, condition=condition)
        
    except Exception as e:
        print(f"[NASA-TLX] Error: {e}")
        return f"エラーが発生しました: {e}", 500

@nasa_tlx_bp.route('/api/nasa_tlx/next_url', methods=['POST'])
def get_next_url():
    """
    クライアントからのリクエストを受け、NASA-TLXへの遷移先URLを生成して返すAPI。
    ページ遷移ロジックをサーバー側に集約するために使用。
    """
    data = request.json
    participant_id = data.get('participant_id', '')
    condition = data.get('condition', '')
    task_type = data.get('task_type', '')

    # URLを生成 (url_forを使ってルート名から生成)
    target_url = url_for('nasa_tlx.page', id=participant_id, con=condition, task=task_type)
    
    return jsonify({
        "redirect_url": target_url
    })