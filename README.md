# ReadMe
## 説明
- HandyKey4VR_FW ( https://github.com/Haru39M/HandyKey4VR_FW.git ) のサーバー側プログラム。
- 指のシーケンスで入力された符号列から全通りの文字列を生成して、N-gram(KenLM)でスコアリングする。
## 環境
- WSL
## KenLMのインストール方法
- https://github.com/kpu/kenlm のREADMEを参照
## N-gramモデルの入手
- wiki_en_token_arpa.binを以下( https://huggingface.co/BramVanroy/kenlm_wikipedia_en )からDLしてルート直下に配置