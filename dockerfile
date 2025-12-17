# ベースイメージ: Python 3.11 (Slim版)
FROM python:3.12-slim-bookworm

# --- 変更点: uv のインストール方法 ---
# 公式のDockerイメージから uv のバイナリだけをコピーします
# これにより pip install uv よりも高速かつ確実に導入できます
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 必要なシステムパッケージのインストール
# kenlmのビルドには build-essential と cmake が必要
# wget はモデルのダウンロードに使用
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係ファイルのコピー
COPY requirements.txt .

# --- 変更なし: uv を使ったインストール ---
# uv pip install --system を使用して、仮想環境を作らずシステムに入れます
# --system オプションはコンテナ内では一般的です
RUN uv pip install --system -r requirements.txt

# N-gramモデルのダウンロード
# RUN wget https://huggingface.co/BramVanroy/kenlm_wikipedia_en/resolve/main/wiki_en_token.arpa.bin -O wiki_en_token.arpa.bin

# ソースコード一式をコピー
COPY . .

# ポートの公開
EXPOSE 5000 8000

# 起動スクリプトの作成
RUN echo '#!/bin/bash\n\
python system/OSCServer.py & \n\
python app.py \n\
' > start.sh && chmod +x start.sh

# コンテナ起動時のコマンド
CMD ["./start.sh"]