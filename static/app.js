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
    const debugMode = document.getElementById('debug-mode');
    const handInput = document.getElementById('handedness');
    const conditionInput = document.getElementById('condition');
    const maxSentencesInput = document.getElementById('max-sentences');

    // Controls
    const btnUp = document.getElementById('btn-up'); 
    const btnDown = document.getElementById('btn-down'); 
    const btnConfirm = document.getElementById('btn-confirm');

    // --- State ---
    let isTestRunning = false;
    let committedWords = [];
    let currentPredictions = []; // Array of {word, score}
    let selectedIndex = -1;
    let autoNextTimer = null;
    
    // Logging Buffer
    let eventLogBuffer = [];

    // --- Keyboard Index Initialization ---
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

    // --- Validation Logic (New) ---
    function checkValidation() {
        if (!startTestBtn) return;
        const isIdValid = debugMode.checked || idInput.value.trim() !== "";
        const isHandSelected = handInput.value !== "";
        const isCondSelected = conditionInput.value !== "";
        const isSentencesValid = maxSentencesInput.value > 0;

        if (isIdValid && isHandSelected && isCondSelected && isSentencesValid) {
            startTestBtn.disabled = false;
            startTestBtn.style.backgroundColor = "#d9534f"; // Original red color
            startTestBtn.style.cursor = "pointer";
        } else {
            startTestBtn.disabled = true;
            startTestBtn.style.backgroundColor = "#ccc";
            startTestBtn.style.cursor = "not-allowed";
        }
    }

    if (idInput) {
        [idInput, debugMode, handInput, conditionInput, maxSentencesInput].forEach(el => {
            el.addEventListener('input', checkValidation);
            el.addEventListener('change', checkValidation);
        });
        // Initial check
        checkValidation();
    }

    // ============================================
    //  LOGGING HELPER
    // ============================================
    function logEvent(type, data) {
        if (!isTestRunning) return;
        eventLogBuffer.push({
            type: type,
            data: data,
            timestamp: Date.now() // Client side timestamp (ms)
        });
    }

    function flushLogs() {
        const logsToSend = [...eventLogBuffer];
        eventLogBuffer = [];
        return logsToSend;
    }

    // ============================================
    //  TEST LOGIC
    // ============================================

    // 1. Start Test
    if (startTestBtn) {
        startTestBtn.addEventListener('click', async () => {
            const pid = debugMode.checked ? "debug-"+idInput.value : idInput.value;
            const hand = handInput.value;
            const params = {
                participant_id: pid,
                condition: conditionInput.value,
                max_sentences: maxSentencesInput.value,
                handedness: hand
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
                eventLogBuffer = []; 
                updateReference(data.reference_text);
                updateProgressDisplay([]);
                renderCandidates();
                
                logEvent('system', 'test_started');

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

        logEvent('system', 'next_phrase_clicked');

        try {
            const logs = flushLogs();
            const res = await fetch('/test/next', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ events: logs })
            });
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

    input.addEventListener('input', async () => {
        const word = input.value.trim();
        
        if (!word) {
            currentPredictions = [];
            selectedIndex = -1;
            renderCandidates();
            updateProgressDisplay(); 
            return;
        }

        try {
            const res = await fetch('/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word: word })
            });
            const data = await res.json();
            
            currentPredictions = data.predictions || [];
            selectedIndex = currentPredictions.length > 0 ? 0 : -1;
            
            logEvent('prediction_update', { count: currentPredictions.length, top: currentPredictions[0]?.word });
            
            renderCandidates();
            updateProgressDisplay(); 

        } catch (e) {
            console.error("Prediction Error:", e);
        }
    });

    input.addEventListener('keydown', (e) => {
        if (!isTestRunning) return;

        logEvent('keydown', { key: e.key, code: e.code });

        if (e.key === 'ArrowRight' || e.key === ' ') {
            e.preventDefault(); 
            moveSelection(1);
        }
        else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            moveSelection(-1);
        }
        else if (e.key === 'Enter') {
            e.preventDefault();
            if (autoNextTimer) {
                goToNextPhrase();
            } else {
                confirmSelection();
            }
        }
        else if (e.key === 'Backspace') {
            if (input.value === '' && committedWords.length > 0) {
                e.preventDefault();
                undoLastWord();
            }
        }
        
        highlightKey(e.key);
    });

    // ============================================
    //  RENDERING & HELPERS
    // ============================================

    function renderCandidates() {
        candidatesRow.innerHTML = '';
        if (currentPredictions.length === 0) return;

        const maxScore = currentPredictions[0].score;
        const minScoreBound = -15.0; 

        currentPredictions.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'candidate-item';
            if (index === selectedIndex) div.classList.add('selected');

            let barPercent = 0;
            if (item.score > minScoreBound) {
                barPercent = Math.max(0, (1 - (item.score / minScoreBound)) * 100); 
            }
            
            div.innerHTML = `
                <div class="candidate-word">${item.word}</div>
                <div class="candidate-score">${item.score.toFixed(2)}</div>
                <div class="score-bar" style="width: ${barPercent}%;"></div>
            `;
            
            div.addEventListener('click', () => {
                logEvent('mouse_select', { index: index, word: item.word });
                selectedIndex = index;
                confirmSelection();
            });

            candidatesRow.appendChild(div);
        });
        
        updateProgressDisplay();
    }

    function moveSelection(dir) {
        if (currentPredictions.length === 0) return;
        selectedIndex += dir;
        
        if (selectedIndex >= currentPredictions.length) selectedIndex = 0;
        if (selectedIndex < 0) selectedIndex = currentPredictions.length - 1;
        
        logEvent('nav', { direction: dir, new_index: selectedIndex });
        renderCandidates();
    }

    function confirmSelection() {
        if (selectedIndex < 0 || !currentPredictions[selectedIndex]) return;
        
        const word = currentPredictions[selectedIndex].word;
        committedWords.push(word);
        
        logEvent('confirm', { word: word });
        
        input.value = '';
        currentPredictions = [];
        selectedIndex = -1;
        renderCandidates();
        
        validateOnServer();
    }

    async function undoLastWord() {
        const removed = committedWords.pop();
        logEvent('undo', { removed_word: removed });
        
        await fetch('/test/backspace', { method: 'POST' });
        
        validateOnServer();
    }

    async function validateOnServer() {
        try {
            const logs = flushLogs();
            const res = await fetch('/test/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    committed_words: committedWords,
                    events: logs 
                })
            });
            const data = await res.json();
            
            updateProgressDisplay(data.results);
            
            if (data.is_completed) {
                handlePhraseCompletion();
            }
        } catch(e) {
            console.error(e);
        }
    }

    function updateProgressDisplay(validatedResults = []) {
        const displayDiv = document.getElementById('progress-text-content');
        
        const sourceData = (validatedResults.length > 0 || committedWords.length === 0) 
                           ? validatedResults 
                           : committedWords.map(w => ({word: w, is_correct: true})); 

        let html = sourceData.map(res => {
            return res.is_correct 
                ? `<span>${res.word}</span>` 
                : `<span class="wrong-word">${res.word}</span>`;
        }).join(" ");

        if (selectedIndex >= 0 && currentPredictions[selectedIndex]) {
            html += ` <span class="current-selection">[${currentPredictions[selectedIndex].word}]</span>`;
        }
        
        displayDiv.innerHTML = html;
    }

    function handlePhraseCompletion() {
        logEvent('system', 'phrase_completed');
        completionMessage.style.display = 'block';
        input.disabled = true;
        nextPhraseBtn.style.display = 'inline-block';
        
        autoNextTimer = setTimeout(goToNextPhrase, 2000);
    }

    function highlightKey(keyChar) {
        const char = keyChar.toLowerCase();
        keyboardKeys.forEach(key => key.classList.remove('active'));
        if (char.length === 1 && char >= 'a' && char <= 'z') {
            const el = document.querySelector(`.key[data-key="${char}"]`);
            if (el) el.classList.add('active');
        }
    }
    input.addEventListener('keyup', () => {
        keyboardKeys.forEach(key => key.classList.remove('active'));
    });
    input.addEventListener('blur', () => {
        keyboardKeys.forEach(key => key.classList.remove('active'));
    });

    if(btnUp) btnUp.addEventListener('click', () => { 
        logEvent('button_click', 'up');
        moveSelection(-1); 
    });
    if(btnDown) btnDown.addEventListener('click', () => { 
        logEvent('button_click', 'down');
        moveSelection(1); 
    });
    if(btnConfirm) btnConfirm.addEventListener('click', () => { 
        logEvent('button_click', 'confirm');
        confirmSelection(); 
    });

});