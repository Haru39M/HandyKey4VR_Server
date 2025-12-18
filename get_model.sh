#!/bin/sh
echo "=== KenLMモデルのダウンロードを開始します ==="
wget https://huggingface.co/BramVanroy/kenlm_wikipedia_en/resolve/main/wiki_en_token.arpa.bin -O wiki_en_token.arpa.bin
echo "=== ダウンロード完了 ==="