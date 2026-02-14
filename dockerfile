# ベースイメージ: Python 3.12 (Bookworm)
FROM python:3.12-slim-bookworm

# uv のバイナリを公式イメージからコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 必要なシステムパッケージのインストール
# kenlmのビルドに build-essential, cmake が必要
# モデル取得用スクリプトのために wget が必要
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# uvの管理ファイルのみを先にコピー
COPY pyproject.toml uv.lock ./

# 依存関係のインストール
# --frozen: ロックファイルの内容を厳密に再現
# --no-cache: キャッシュを残さずイメージサイズ削減
RUN uv sync --frozen --no-cache

# ソースコード一式をコピー
# (.dockerignore で不要なものは除外されている前提)
COPY . .

# ポートの公開
EXPOSE 5000 8000

# 環境変数の設定
# uv は仮想環境(.venv)を作成するため、パスを通す
ENV PATH="/app/.venv/bin:$PATH"

# 起動スクリプトの作成
RUN echo '#!/bin/bash\n\
python app.py \n\
' > start.sh && chmod +x start.sh

# コンテナ起動時のコマンド
CMD ["./start.sh"]