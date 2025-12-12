// static/app.js

document.addEventListener('DOMContentLoaded', () => {

    // --- DOM要素 ---
    const input = document.getElementById('word-input');
    const resultsContainer = document.getElementById('results-container');
    const infoContainer = document.getElementById('info-container');
    const keyboardKeys = document.querySelectorAll('#keyboard-container .key');

    // Test Mode Elements
    const startTestBtn = document.getElementById('start-test-btn');
    const nextPhraseBtn = document.getElementById('next-phrase-btn');
    const referenceDisplay = document.getElementById('reference-display');
    const referenceTextContent = document.getElementById('reference-text-content');
    const progressDisplay = document.getElementById('progress-display');
    const progressTextContent = document.getElementById('progress-text-content');

    const btnUp = document.getElementById('btn-up');
    const btnDown = document.getElementById('btn-down');
    const btnConfirm = document.getElementById('btn-confirm');

    // --- State Variables ---
    let isTestMode = false;
    let committedWords = []; // 入力確定した単語リスト
    let currentPredictions = [];
    let selectedIndex = -1;

    // バックエンドから受け取る状態
    let validatedResults = []; // {word: "...", is_correct: true/false} のリスト
    let isCompleted = false;

    // --- 初期化 ---
    keyboardKeys.forEach(keyElement => {
        const char = keyElement.dataset.key;
        if (char && typeof REVERSE_QWERTY_MAP !== 'undefined' && REVERSE_QWERTY_MAP[char]) {
            const indexLabel = keyElement.querySelector('.index-label');
            if (indexLabel) indexLabel.textContent = REVERSE_QWERTY_MAP[char];
        }
    });

    // ==========================================
    // タイピングテスト操作
    // ==========================================

    startTestBtn.addEventListener('click', startTest);
    nextPhraseBtn.addEventListener('click', nextPhrase);

    async function startTest() {
        isTestMode = true;
        resetSession();

        // UI表示切り替え
        referenceDisplay.style.display = 'block';
        progressDisplay.style.display = 'block';
        startTestBtn.style.display = 'none';
        nextPhraseBtn.style.display = 'none';

        try {
            const response = await fetch('/test/start', { method: 'POST' });
            const data = await response.json();
            referenceTextContent.textContent = data.reference_text;
            input.focus();
        } catch (e) {
            console.error(e);
            alert("Connection Error");
        }
    }

    async function nextPhrase() {
        resetSession();
        nextPhraseBtn.style.display = 'none';
        resultsContainer.innerHTML = '<p class="no-results">...</p>';

        try {
            const response = await fetch('/test/next', { method: 'POST' });
            const data = await response.json();
            referenceTextContent.textContent = data.reference_text;
            input.focus();
        } catch (e) {
            console.error(e);
        }
    }

    function resetSession() {
        committedWords = [];
        validatedResults = [];
        isCompleted = false;
        resetInput();
        updateDisplay();
    }

    // ==========================================
    // バックエンド同期 & 描画
    // ==========================================

    /**
     * バックエンドに入力状態を送信し、正誤判定を受け取る
     */
    async function validateInputOnServer() {
        try {
            const response = await fetch('/test/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ committed_words: committedWords })
            });
            const data = await response.json();

            // サーバーからの評価結果で状態を更新
            validatedResults = data.results;
            isCompleted = data.is_completed;

            updateDisplay();

            if (isCompleted) {
                nextPhraseBtn.style.display = 'inline-block';
                resultsContainer.innerHTML = '<p class="info">正解！次の文章に進んでください。</p>';
                input.value = ''; // 入力をクリア
                input.blur();
            }

        } catch (e) {
            console.error("Validation API Error:", e);
        }
    }

    /**
     * 現在の状態に基づいて表示を更新する
     * ロジック（判定）は含まず、状態の描画のみ行う
     */
    function updateDisplay() {
        // 確定済み単語の表示（サーバーの判定結果に基づく）
        let htmlParts = validatedResults.map(res => {
            const escapedWord = escapeHTML(res.word);
            if (!res.is_correct) {
                return `<span class="wrong-word">${escapedWord}</span>`;
            } else {
                return escapedWord;
            }
        });

        // 現在選択中の予測候補（プレビュー）
        if (!isCompleted && selectedIndex >= 0 && currentPredictions[selectedIndex]) {
            const currentWord = currentPredictions[selectedIndex];
            htmlParts.push(`<span class="current-selection">[${escapeHTML(currentWord)}]</span>`);
        }

        progressTextContent.innerHTML = htmlParts.join(" ");
    }

    // ==========================================
    // 入力・予測・操作
    // ==========================================

    input.addEventListener('keydown', (e) => {
        if (isCompleted) return; // 完了してたら入力させない

        // Space: 候補ループ選択 (下へ)
        if (e.key === ' ') {
            e.preventDefault();
            moveSelection(1);
            return;
        }

        // Backspace: 空欄時に確定単語を戻す
        if (e.key === 'Backspace') {
            if (input.value === '' && committedWords.length > 0) {
                e.preventDefault();
                const lastWord = committedWords.pop();
                input.value = lastWord; // 入力欄に戻す

                // 変更をサーバーに通知（同期）
                validateInputOnServer();

                // 予測も再開
                input.dispatchEvent(new Event('input'));
                return;
            }
        }

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            moveSelection(1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            moveSelection(-1);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            confirmSelection();
        }
    });

    input.addEventListener('input', async () => {
        const word = input.value.trim();
        if (!word) {
            currentPredictions = [];
            selectedIndex = -1;
            renderCandidates();
            updateDisplay();
            return;
        }

        // 予測API
        try {
            const response = await fetch('/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word: word }),
            });
            const data = await response.json();

            if (data.predictions) {
                currentPredictions = data.predictions;
                selectedIndex = currentPredictions.length > 0 ? 0 : -1;
            } else {
                currentPredictions = [];
                selectedIndex = -1;
            }

            renderCandidates();
            updateDisplay();

            if (data.converted_index) {
                infoContainer.innerHTML = `<span class="info-small">Index: ${data.converted_index}</span>`;
            }

        } catch (error) {
            console.error(error);
        }
    });

    // キーボードハイライト
    input.addEventListener('keydown', (e) => {
        const char = e.key.toLowerCase();
        if (e.repeat) return;
        keyboardKeys.forEach(key => key.classList.remove('active'));
        if (char.length === 1 && char >= 'a' && char <= 'z') {
            const targetKey = document.querySelector(`.key[data-key="${char}"]`);
            if (targetKey) targetKey.classList.add('active');
        }
    });
    input.addEventListener('blur', () => {
        keyboardKeys.forEach(key => key.classList.remove('active'));
    });

    // --- 補助関数 ---

    function moveSelection(direction) {
        if (currentPredictions.length === 0) return;
        selectedIndex += direction;
        // ループ処理
        if (selectedIndex >= currentPredictions.length) selectedIndex = 0;
        if (selectedIndex < 0) selectedIndex = currentPredictions.length - 1;

        renderCandidates();
        updateDisplay();
    }

    function confirmSelection() {
        if (selectedIndex < 0 || !currentPredictions[selectedIndex]) return;

        const selectedWord = currentPredictions[selectedIndex];
        committedWords.push(selectedWord);

        // 入力をリセットして、サーバーへ同期
        input.value = '';
        currentPredictions = [];
        selectedIndex = -1;
        infoContainer.innerHTML = '';
        renderCandidates();

        validateInputOnServer();
    }

    function resetInput() {
        input.value = '';
        currentPredictions = [];
        selectedIndex = -1;
        infoContainer.innerHTML = '';
        renderCandidates();
    }

    function renderCandidates() {
        resultsContainer.innerHTML = '';
        if (currentPredictions.length === 0) {
            resultsContainer.innerHTML = '<p class="no-results">候補なし</p>';
            return;
        }

        const ul = document.createElement('ul');
        currentPredictions.forEach((pred, index) => {
            const li = document.createElement('li');
            li.textContent = pred;
            if (index === selectedIndex) li.classList.add('selected');

            li.addEventListener('click', () => {
                selectedIndex = index;
                confirmSelection();
            });
            ul.appendChild(li);
        });
        resultsContainer.appendChild(ul);
    }

    // ボタンUI
    btnUp.addEventListener('click', () => moveSelection(-1));
    btnDown.addEventListener('click', () => moveSelection(1));
    btnConfirm.addEventListener('click', confirmSelection);
});

function escapeHTML(str) {
    if (typeof str !== 'string') return str;
    return str.replace(/[&<>"']/g, match => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[match]);
}