# ReadMe
## 説明
- HandyKey4VR_FW ( https://github.com/Haru39M/HandyKey4VR_FW.git ) のサーバー側プログラム。
- 指のシーケンスで入力された符号列から全通りの文字列を生成して、N-gram(KenLM)でスコアリングする。
## 環境構築(Dockerを利用する場合)
- Docker Desktopをインストール
- dockerイメージを以下のコマンドで落とす
```bash
$ docker pull haru39m/handykey4vr-demo
```
- コンテナを起動
## 環境構築(WSL or Linux)
- リポジトリをCloneする
- 仮想環境を有効化
```bash
$ source .venv/bin/activate
```

## 使い方(タイピング)
- デバイス(HandyKey4VR_R/L)をBluetoothでペアリング
- コンテナを起動し，ブラウザからlocalhost:5000へアクセス
<!-- 
```bash
$ pip install flask python-osc
```
## KenLMのインストール方法
- https://github.com/kpu/kenlm のREADMEを参照
## N-gramモデルの入手
- wiki_en_token_arpa.binを以下( https://huggingface.co/BramVanroy/kenlm_wikipedia_en )からDLしてルート直下に配置 -->