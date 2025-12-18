import requests

class VRChatTypingDisplay:
    def __init__(self, endpoint = "127.0.0.1",port=3000):
        """
        初期化
        :param port: ツールが待受しているポート番号 (デフォルト: 3000)
        """
        # self.base_url = f"http://100.97.18.118:{port}/send"
        self.base_url = f"http://{endpoint}:{port}/send"
        self.CANDIDATE_COUNT = 6

    def _format_candidate_line(self, word, is_selected):
        """
        中央揃え対策として、選択状態による文字幅のズレを吸収する整形を行う
        """
        if is_selected:
            # 選択中は目立つ記号をつける
            return f"=> {word} <="
        else:
            # 非選択時は全角スペース等でパディングして視覚的な高さを揃える
            return f"{word}"

    def update_display(self, teacher_text, candidates, selected_index):
        """
        ChatBoxの表示を更新する関数
        """
        if len(candidates) != self.CANDIDATE_COUNT:
            candidates = (candidates + [""] * 6)[:6]

        safe_index = max(0, min(selected_index, self.CANDIDATE_COUNT - 1))
        current_word = candidates[safe_index]

        # 表示用テキストリストの構築
        lines = []
        
        # 1行目: 教師テキスト
        lines.append(teacher_text)
        
        # 2行目: 選択中の単語
        lines.append(f"[ {current_word} ]")
        
        # 3行目～8行目: 候補リスト
        for i, word in enumerate(candidates):
            line_str = self._format_candidate_line(word, i == safe_index)
            lines.append(line_str)
            
        # 9行目: 調整用
        lines.append(" ") 

        # 【修正点】: 改行コードではなく、文字列のリテラル "\n" で結合する
        # これにより、URL上では "...row1\nrow2..." のように送られることを意図しています
        full_text = "\\n".join(lines)
        
        # 送信処理
        self._send_request(full_text)

    def _send_request(self, text):
        """
        ツールへGETリクエストを送信する
        """
        try:
            # 【修正点】: params引数を使ってrequestsにエンコードを任せる
            # これにより "?text=A%5CnB" (A\nB) のような形式で安全に送信されます
            params = {'text': text}
            requests.get(self.base_url, params=params, timeout=0.5)
            
        except requests.exceptions.RequestException as e:
            print(f"[Display Error] Failed to send text to VRChat: {e}")

# テスト実行用
if __name__ == "__main__":
    display = VRChatTypingDisplay()
    sample_teacher = "Test Teacher Text"
    sample_candidates = ["Word1", "Word2", "Word3", "Word4", "Word5", "Word6"]
    
    print("Sending test request with literal \\n...")
    display.update_display(sample_teacher, sample_candidates, 4)
    print("Done.")