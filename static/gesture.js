document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-btn');
    const configSection = document.getElementById('config-section');
    const testSection = document.getElementById('test-section');
    const finishedScreen = document.getElementById('finished-screen');
    
    // Config Inputs
    const idInput = document.getElementById('participant-id');
    const debugMode = document.getElementById('debug-mode');
    const handInput = document.getElementById('handedness');
    const condInput = document.getElementById('condition');
    const trialsInput = document.getElementById('max-trials');

    const targetImg = document.getElementById('target-img');
    const targetName = document.getElementById('target-name');
    const targetDesc = document.getElementById('target-desc');
    const matchIndicator = document.getElementById('match-indicator');
    const progressText = document.getElementById('progress-text');
    
    const overlay = document.getElementById('overlay-message');
    const overlayText = document.getElementById('overlay-text');

    const fingerIds = ['T', 'I', 'M', 'R', 'P'];
    let pollingInterval = null;

    // --- State Management for Logging ---
    let isTestRunning = false;
    let eventLogBuffer = [];
    let lastState = "IDLE"; // ステート遷移検知用

    // ============================================
    //  CONFIG VALIDATION
    // ============================================
    function checkConfigValidity() {
        const idVal = idInput.value.trim();
        const handVal = handInput.value;
        const condVal = condInput.value;
        
        // CSSの :disabled 疑似クラスにスタイルを任せるため、
        // JSでは disabled プロパティの切り替えのみを行います。
        if (idVal && handVal && condVal) {
            startBtn.disabled = false;
        } else {
            startBtn.disabled = true;
        }
    }

    idInput.addEventListener('input', checkConfigValidity);
    handInput.addEventListener('change', checkConfigValidity);
    condInput.addEventListener('change', checkConfigValidity);
    checkConfigValidity();

    // ============================================
    //  LOGGING HELPER
    // ============================================
    function logEvent(type, data) {
        if (!isTestRunning && type !== 'system') return;
        
        eventLogBuffer.push({
            type: type,
            data: data, 
            timestamp: Date.now() 
        });

        if (eventLogBuffer.length >= 5 || type === 'state_change' || type === 'state_input') {
            uploadLogs();
        }
    }

    async function uploadLogs() {
        if (eventLogBuffer.length === 0) return;

        const dataToSend = [...eventLogBuffer];
        eventLogBuffer = []; 

        try {
            await fetch('/gesture/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dataToSend)
            });
        } catch (e) {
            console.error("Log upload failed:", e);
            eventLogBuffer = [...dataToSend, ...eventLogBuffer];
        }
    }

    // ============================================
    //  TEST FLOW
    // ============================================

    startBtn.addEventListener('click', async () => {
        if (startBtn.disabled) return;

        const pId = idInput.value.trim();
        const handVal = handInput.value;
        const condVal = condInput.value;
        
        const finalId = debugMode.checked && !pId.includes('debug') ? `debug-${pId}` : pId;

        const config = {
            participant_id: finalId,
            condition: condVal,
            handedness: handVal,
            max_trials: parseInt(trialsInput.value)
        };

        logEvent('system', JSON.stringify({ 
            action: "test_start_click",
            participant_id: finalId,
            condition: config.condition
        }));

        try {
            const res = await fetch('/gesture/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            if (!res.ok) {
                const errText = await res.text();
                throw new Error(`Server Error (${res.status}):\n${errText}`);
            }

            const data = await res.json();
            
            if (data.status === 'started') {
                isTestRunning = true;
                configSection.style.display = 'none';
                testSection.style.display = 'block';
                startPolling();
            } else {
                throw new Error("Unknown status received from server");
            }
        } catch (e) {
            console.error(e);
            alert(`Failed to start test:\n${e.message}`);
        }
    });

    function startPolling() {
        if (pollingInterval) clearInterval(pollingInterval);
        pollingInterval = setInterval(checkState, 100); 
    }

    async function checkState() {
        try {
            const res = await fetch('/gesture/state');
            if (!res.ok) {
                // サーバーダウン時などの処理
                console.warn("Polling response not OK:", res.status);
                return;
            }
            const data = await res.json(); 

            // ★サーバーがIDLEに戻っている（再起動された）場合の検知
            if (isTestRunning && data.state === 'IDLE') {
                alert("Server reset detected. The test will be aborted. Please start again.");
                resetToConfig();
                return;
            }

            progressText.textContent = `Trial: ${data.current_trial} / ${data.total_trials}`;
            
            if (data.current_input) {
                updateHandStatus(data.current_input);
            }

            // State Change Detection & Logging
            if (lastState !== data.state) {
                logEvent('state_change', JSON.stringify({
                    from: lastState,
                    to: data.state
                }));

                if (data.current_input) {
                    logEvent('state_input', JSON.stringify(data.current_input));
                }

                lastState = data.state;
            }

            // State Handling
            if (data.state === 'COMPLETED') {
                finishTest();
                return;
            }

            if (data.state === 'WAIT_HAND_OPEN') {
                overlay.style.display = 'flex';
                overlayText.textContent = "Please Open Hand";
                matchIndicator.style.visibility = 'hidden';
                // 念のため画像を隠す（前の画像が残らないようにする場合）
                targetImg.style.display = 'none';
            } else if (data.state === 'COUNTDOWN') {
                overlay.style.display = 'flex';
                overlayText.textContent = `Get Ready... ${Math.ceil(data.countdown_remaining)}`;
                matchIndicator.style.visibility = 'hidden';
            } else if (data.state === 'MEASURING') {
                overlay.style.display = 'none';
                matchIndicator.style.visibility = 'visible';

                if (data.target) {
                    let imgName = data.target.Image;
                    if (!imgName) {
                        imgName = `gesture_${data.target.GestureName.toLowerCase()}.png`;
                    }
                    if (targetImg.src.indexOf(imgName) === -1) {
                        targetImg.src = `/gesture_images/${imgName}`;
                    }
                    
                    // 【修正箇所】ここで画像を表示状態にする
                    targetImg.style.display = 'inline-block';

                    targetName.textContent = data.target.GestureName;
                    targetDesc.textContent = data.target.Description || "";
                }

                if (data.is_match) {
                    matchIndicator.textContent = "MATCH";
                    matchIndicator.className = "indicator match";
                } else {
                    matchIndicator.textContent = "GO!";
                    matchIndicator.className = "indicator mismatch";
                }
            }

        } catch (e) {
            console.error("Polling error:", e);
        }
    }

    function updateHandStatus(inputData) {
        fingerIds.forEach(fid => {
            const el = document.getElementById(`f-${fid}`).querySelector('.f-val');
            const val = inputData[fid];
            el.textContent = val || "---";
            
            if (val === 'OPEN') el.style.color = '#4caf50';
            else if (val === 'CLOSE') el.style.color = '#f44336';
            else el.style.color = '#ccc';
        });
    }

    async function finishTest() {
        clearInterval(pollingInterval);
        logEvent('system', 'test_finished');
        await uploadLogs(); 
        
        isTestRunning = false;
        testSection.style.display = 'none';
        finishedScreen.style.display = 'block';
    }

    function resetToConfig() {
        clearInterval(pollingInterval);
        isTestRunning = false;
        configSection.style.display = 'flex';
        testSection.style.display = 'none';
        finishedScreen.style.display = 'none';
        
        // リセット時に画像も隠す
        targetImg.style.display = 'none';
        targetImg.src = "";
        
        lastState = "IDLE";
        checkConfigValidity(); // ボタン状態更新
    }
});