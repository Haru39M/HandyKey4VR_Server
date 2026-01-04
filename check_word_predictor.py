from word_predictor import WordPredictor
from typing_test import TypingTest

if __name__ == "__main__":
    model_path = 'wiki_en_token.arpa.bin'
    predictor = WordPredictor(model_path)

    tester = TypingTest()
    tester.loadPhraseSet('phrases2.txt')
    tester.max_sentences = 500
    miss_words = []
    while tester.current_sentence_index < tester.max_sentences:
        tester.loadReferenceText()
        text = tester.getReferenceText().split()
        print(f"checking sentence {tester.current_sentence_index}")
        for word in text:
            predictor.set_text_input(word)
            predicted_words = predictor.predict_top_words(limit=10,beam_width=10000)
            if not (word.lower() in predicted_words):
                print(f"nothing word in predicted! > {word}")
                miss_words.append('{'+word+":"+str(tester.current_sentence_index)+'}')
    print(miss_words)
