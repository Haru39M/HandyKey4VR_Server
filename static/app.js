document.addEventListener('DOMContentLoaded', () => {

    // --- DOM Elements ---
    const input = document.getElementById('word-input');
    const candidatesRow = document.getElementById('horizontal-candidates');
    const keyboardKeys = document.querySelectorAll('#keyboard-container .key');

    // UI Sections
    const startTestBtn = document.getElementById('start-test-btn');
    const nextPhraseBtn = document.getElementById('next-phrase-btn');
    const configSection = document.getElementById('config-section');
    const testSection = document.getElementById('test-section');
    const completionMessage = document.getElementById('completion-message');

    // Config Inputs
    const idInput = document.getElementById('participant-id');
    const conditionInput = document.getElementById('condition');
    const maxSentencesInput = document.getElementById('max-sentences');

    // Controls
    const btnUp = document.getElementById('btn-up'); // 画面上の矢印(←)
    const btnDown = document.getElementById('btn-down'); // 画面上の矢印(→)
    const btnConfirm = document.getElementById('btn-confirm');

    // --- State ---
    let isTestRunning = false;
    let committedWords = [];
    let currentPredictions = []; // Array of {word, score}
    let selectedIndex = -1;
    let autoNextTimer = null;

    // --- Keyboard Index Initialization ---
    // REVERSE_QWERTY_MAPはHTML内のScriptタグで定義済み
    if (typeof REVERSE_QWERTY_MAP !== 'undefined') {
        keyboardKeys.forEach(keyElement => {
            const char = keyElement.dataset.key;
            if (char && REVERSE_QWERTY_MAP[char]) {
                const indexLabel = keyElement.querySelector('.index-label');
                if (indexLabel) {
                    indexLabel.textContent = REVERSE_QWERTY_MAP[char];
                }
            }
        });
    }

    // ============================================
    //  TEST LOGIC
    // ============================================

    // 1. Start Test
    if (startTestBtn) {
        startTestBtn.addEventListener('click', async () => {
            console.log("Start button clicked");

            const params = {
                participant_id: idInput.value,
                condition: conditionInput.value,
                max_sentences: maxSentencesInput.value
            };

            try {
                const res = await fetch('/test/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(params)
                });

                if (!res.ok) throw new Error("API Response not ok");

                const data = await res.json();

                // Switch UI
                isTestRunning = true;
                configSection.style.display = 'none';
                testSection.style.display = 'block';
                input.disabled = false;
                input.value = '';
                input.focus();

                // Initialize Session
                committedWords = [];
                currentPredictions = [];
                updateReference(data.reference_text);
                updateProgressDisplay([]);
                renderCandidates();

            } catch (e) {
                console.error("Start Test Error:", e);
                alert("テストの開始に失敗しました。サーバーを確認してください。");
            }
        });
    }

    // 2. Next Phrase (Manual or Auto)
    async function goToNextPhrase() {
        if (autoNextTimer) clearTimeout(autoNextTimer);
        autoNextTimer = null;
        completionMessage.style.display = 'none';
        nextPhraseBtn.style.display = 'none';

        try {
            const res = await fetch('/test/next', { method: 'POST' });
            const data = await res.json();

            updateReference(data.reference_text);

            if (data.reference_text !== "TEST_FINISHED") {
                committedWords = [];
                input.value = '';
                input.disabled = false;
                input.focus();
                updateProgressDisplay([]);
                renderCandidates();
            }
        } catch (e) {
            console.error(e);
        }
    }

    if (nextPhraseBtn) {
        nextPhraseBtn.addEventListener('click', goToNextPhrase);
    }

    function updateReference(text) {
        const refContent = document.getElementById('reference-text-content');
        if (text === "TEST_FINISHED") {
            testSection.innerHTML = '<div class="finished-screen">TEST FINISHED<br><small>Thank you!</small></div>';
            input.disabled = true;
            isTestRunning = false;
        } else {
            refContent.textContent = text;
        }
    }

    // ============================================
    //  INPUT & PREDICTION LOGIC
    // ============================================

    // Input Event
    input.addEventListener('input', async () => {
        const word = input.value.trim();

        if (!word) {
            currentPredictions = [];
            selectedIndex = -1;
            renderCandidates();
            updateProgressDisplay(); // clear preview
            return;
        }

        try {
            // Call Predict API
            const res = await fetch('/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word: word })
            });
            const data = await res.json();

            // data.predictions contains [{word: "...", score: -1.2}, ...]
            currentPredictions = data.predictions || [];

            // Auto-select first candidate if available
            selectedIndex = currentPredictions.length > 0 ? 0 : -1;

            renderCandidates();
            updateProgressDisplay();

        } catch (e) {
            console.error("Prediction Error:", e);
        }
    });

    // KeyDown Handling
    input.addEventListener('keydown', (e) => {
        if (!isTestRunning) return;

        // Navigation: Right Arrow or Space -> Next Candidate
        if (e.key === 'ArrowRight' || e.key === ' ') {
            e.preventDefault(); // Prevent space typing
            moveSelection(1);
        }
        // Navigation: Left Arrow -> Prev Candidate
        else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            moveSelection(-1);
        }
        // Confirm: Enter
        else if (e.key === 'Enter') {
            e.preventDefault();
            // If waiting for auto-next, skip wait
            if (autoNextTimer) {
                goToNextPhrase();
            } else {
                confirmSelection();
            }
        }
        // Undo: Backspace (only if input is empty)
        else if (e.key === 'Backspace') {
            if (input.value === '' && committedWords.length > 0) {
                e.preventDefault();
                undoLastWord();
            }
        }
    });

    // ============================================
    //  RENDERING & HELPERS
    // ============================================

    function renderCandidates() {
        candidatesRow.innerHTML = '';
        if (currentPredictions.length === 0) return;

        // Determine min/max for score bar
        // KenLM scores are log10 probabilities (usually negative, closer to 0 is better)
        // e.g., -0.5 (good) to -6.0 (bad)
        const maxScore = currentPredictions[0].score;
        // Use a fixed floor for visualization or dynamic range
        const minScoreBound = -15.0;

        currentPredictions.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'candidate-item';
            if (index === selectedIndex) div.classList.add('selected');

            // Calculate bar width (0% to 100%)
            let barPercent = 0;
            if (item.score > minScoreBound) {
                // Linear interpolation: (score - min) / (max - min) roughly?
                // Actually, just mapping score to percentage against a floor works visually
                // 0 (top) -> 100%, -15 (floor) -> 0%
                barPercent = Math.max(0, (1 - (item.score / minScoreBound)) * 100);
                // Since scores are negative: item.score / minScoreBound is positive (e.g., -3 / -15 = 0.2)
                // 1 - 0.2 = 0.8 (80%) -> Logic check:
                // If score is -3 (high), -3/-15 = 0.2. We want high bar.
                // If score is -15 (low), -15/-15 = 1. We want low bar.
                // Formula: (1 - (item.score / minScoreBound)) * 100 IS correct if we want higher score = larger bar.
            }
            // Better visual formula: 
            // Percentage = 100 - ( (maxScore - item.score) / range * 100 ) ?
            // Let's stick to simple relative check against specific floor.

            div.innerHTML = `
                <div class="candidate-word">${item.word}</div>
                <div class="candidate-score">${item.score.toFixed(2)}</div>
                <div class="score-bar" style="width: ${barPercent}%;"></div>
            `;

            // Mouse click support
            div.addEventListener('click', () => {
                selectedIndex = index;
                confirmSelection();
            });

            candidatesRow.appendChild(div);
        });

        // Update preview to show selection
        updateProgressDisplay();
    }

    function moveSelection(dir) {
        if (currentPredictions.length === 0) return;
        selectedIndex += dir;

        // Loop around
        if (selectedIndex >= currentPredictions.length) selectedIndex = 0;
        if (selectedIndex < 0) selectedIndex = currentPredictions.length - 1;

        renderCandidates();
    }

    function confirmSelection() {
        if (selectedIndex < 0 || !currentPredictions[selectedIndex]) return;

        const word = currentPredictions[selectedIndex].word;
        committedWords.push(word);

        // Reset input state
        input.value = '';
        currentPredictions = [];
        selectedIndex = -1;
        renderCandidates();

        // Sync with server
        validateOnServer();
    }

    async function undoLastWord() {
        committedWords.pop();

        // Notify server for logging
        await fetch('/test/backspace', { method: 'POST' });

        validateOnServer();
    }

    async function validateOnServer() {
        try {
            const res = await fetch('/test/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ committed_words: committedWords })
            });
            const data = await res.json();

            // Update UI with server validation (red/black text)
            updateProgressDisplay(data.results);

            if (data.is_completed) {
                handlePhraseCompletion();
            }
        } catch (e) {
            console.error(e);
        }
    }

    function updateProgressDisplay(validatedResults = []) {
        const displayDiv = document.getElementById('progress-text-content');

        // If we have validation results, use them. Otherwise use local committedWords (all assumed correct temporarily)
        const sourceData = (validatedResults.length > 0 || committedWords.length === 0)
            ? validatedResults
            : committedWords.map(w => ({ word: w, is_correct: true })); // fallback

        let html = sourceData.map(res => {
            return res.is_correct
                ? `<span>${res.word}</span>`
                : `<span class="wrong-word">${res.word}</span>`;
        }).join(" ");

        // Append current selection preview
        if (selectedIndex >= 0 && currentPredictions[selectedIndex]) {
            html += ` <span class="current-selection">[${currentPredictions[selectedIndex].word}]</span>`;
        }

        displayDiv.innerHTML = html;
    }

    function handlePhraseCompletion() {
        completionMessage.style.display = 'block';
        input.disabled = true;
        // Show manual next button as well
        nextPhraseBtn.style.display = 'inline-block';

        // Auto next in 2 seconds
        autoNextTimer = setTimeout(goToNextPhrase, 2000);
    }

    // --- Keyboard Visual Feedback (Preserved) ---
    input.addEventListener('keydown', (e) => {
        const char = e.key.toLowerCase();
        if (e.repeat) return;
        keyboardKeys.forEach(key => key.classList.remove('active'));
        if (char.length === 1 && char >= 'a' && char <= 'z') {
            const el = document.querySelector(`.key[data-key="${char}"]`);
            if (el) el.classList.add('active');
        }
    });
    input.addEventListener('keyup', () => {
        keyboardKeys.forEach(key => key.classList.remove('active'));
    });
    input.addEventListener('blur', () => {
        keyboardKeys.forEach(key => key.classList.remove('active'));
    });

    // --- On-Screen Buttons ---
    if (btnUp) btnUp.addEventListener('click', () => moveSelection(-1));
    if (btnDown) btnDown.addEventListener('click', () => moveSelection(1));
    if (btnConfirm) btnConfirm.addEventListener('click', confirmSelection);

});