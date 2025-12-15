import kenlm
import time
def evaluate_sentence(sentence):
    score = model.score(sentence,bos=True,eos=True)
    print(f"{sentence}:{score}")

# model = kenlm.Model('kenlm/lm/test.arpa')
model = kenlm.LanguageModel('wiki_en_token.arpa.bin')
# start = time.perf_counter()
# print(model.score('start over', bos = True, eos = True))
# print(model.score('strat over', bos = True, eos = True))
# print(model.score('this is a sentence .', bos = True, eos = True))
# print(model.score('nls', bos = True, eos = True))
# print(model.score('now', bos = True, eos = True))
evaluate_sentence('nls')
evaluate_sentence('now')
# end = time.perf_counter() #計測終了
# print('{:.2f}'.format((end-start))) # 87.97(秒→分に直し、小数点以下の桁数を指定して出力)