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
    //  LOGGING HELPER (app.jsと同様の実装)
    // ============================================
    function logEvent(type, data) {
        if (!isTestRunning && type !== 'system') return; // systemイベントはtest開始前でも許可する場合あり
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

    async function uploadLogs() {
        const logs = flushLogs();
        if (logs.length === 0) return;

        try {
            // ログ送信専用のエンドポイントへPOST（サーバー側で実装が必要）
            // または、既存の通信に乗せる設計の場合はそれに合わせる
            await fetch('/gesture/log', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ events: logs })
            });
        } catch (e) {
            console.error("Log upload failed:", e);
            // 送信失敗時はバッファに戻す簡易実装（順序が狂う可能性があるため、本番ではより厳密なQueue管理が必要）
            // ここでは簡易的にエラーログのみ
        }
    }

    // --- Validation Logic ---
    function checkValidation() {
        const isIdValid = debugMode.checked || idInput.value.trim() !== "";
        const isHandSelected = handInput.value !== "";
        const isCondSelected = condInput.value !== "";
        const isTrialsValid = trialsInput.value > 0;

        if (isIdValid && isHandSelected && isCondSelected && isTrialsValid) {
            startBtn.disabled = false;
            startBtn.style.backgroundColor = "#007bff";
            startBtn.style.cursor = "pointer";
        } else {
            startBtn.disabled = true;
            startBtn.style.backgroundColor = "#ccc";
            startBtn.style.cursor = "not-allowed";
        }
    }

    [idInput, debugMode, handInput, condInput, trialsInput].forEach(el => {
        el.addEventListener('input', checkValidation);
        el.addEventListener('change', checkValidation);
    });

    // テスト開始
    startBtn.addEventListener('click', async () => {
        const pid = debugMode.checked ? "debug-"+idInput.value : idInput.value;
        const hand = handInput.value;
        const cond = condInput.value;
        const maxTrials = trialsInput.value;

        // Startイベントをログ
        logEvent('system', { 
            action: 'test_start_click',
            participant_id: pid,
            condition: cond
        });

        try {
            await fetch('/gesture/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    participant_id: pid,
                    condition: cond,
                    max_trials: maxTrials,
                    handedness: hand
                })
            });

            isTestRunning = true;
            configSection.style.display = 'none';
            testSection.style.display = 'block';
            
            if (pollingInterval) clearInterval(pollingInterval);
            // ステート更新とログ送信を行うループを開始
            pollingInterval = setInterval(async () => {
                await updateState();
                await uploadLogs(); // バッファがあれば送信
            }, 100);

        } catch (e) {
            console.error(e);
            alert("Error starting test");
        }
    });

    async function updateState() {
        try {
            const res = await fetch('/gesture/state');
            const data = await res.json();

            // --- ステート遷移の検知とロギング ---
            if (data.state !== lastState) {
                logEvent('state_change', { from: lastState, to: data.state });
                
                // MEASURINGになった瞬間 = ターゲット画像が表示された瞬間
                if (data.state === "MEASURING" && data.target) {
                    logEvent('stimulus_shown', { 
                        target_name: data.target.GestureName,
                        target_id: data.target.GestureID // IDがあれば
                    });
                }
                lastState = data.state;
            }

            if (!data.is_running && data.state === "COMPLETED") {
                finishTest();
                return;
            }

            if (data.progress) progressText.textContent = data.progress;

            if (data.current_input) {
                fingerIds.forEach(fid => {
                    const el = document.querySelector(`#f-${fid} .f-val`);
                    const val = data.current_input[fid];
                    el.textContent = val;
                });
            }

            // --- ステートごとの表示制御 ---
            if (data.state === "WAIT_HAND_OPEN") {
                overlay.style.display = "flex";
                overlayText.textContent = "Please Open Hand";
                targetImg.style.display = "none";
                targetName.textContent = "???";
                targetDesc.textContent = "Waiting...";
                matchIndicator.textContent = "WAIT";
                matchIndicator.className = "indicator mismatch";

            } else if (data.state === "COUNTDOWN") {
                overlay.style.display = "flex";
                targetImg.style.display = "none";
                
                const remaining = Math.ceil(data.countdown_remaining);
                overlayText.textContent = remaining > 0 ? remaining : "START!";
                
            } else if (data.state === "MEASURING") {
                overlay.style.display = "none";
                targetImg.style.display = "inline";

                if (data.target) {
                    let imgName = data.target.Image;
                    if (!imgName) {
                        imgName = `gesture_${data.target.GestureName.toLowerCase()}.png`;
                    }
                    // 画像のsrc変更を検知したい場合は、onloadイベントでログを取るのも有効
                    if (targetImg.src.indexOf(imgName) === -1) {
                        targetImg.src = `/gesture_images/${imgName}`;
                    }
                    targetName.textContent = data.target.GestureName;
                    targetDesc.textContent = data.target.Description || "";
                }

                if (data.is_match) {
                    matchIndicator.textContent = "MATCH";
                    matchIndicator.className = "indicator match";
                    // マッチした瞬間をクライアント側でも記録したければここでもログ可能
                    // ただし、サーバー側で判定しているので冗長になる可能性あり
                } else {
                    matchIndicator.textContent = "GO!";
                    matchIndicator.className = "indicator mismatch";
                }
            }

        } catch (e) {
            console.error("Polling error:", e);
        }
    }

    async function finishTest() {
        clearInterval(pollingInterval);
        logEvent('system', 'test_finished');
        await uploadLogs(); // 最後のログを送信
        
        isTestRunning = false;
        testSection.style.display = 'none';
        finishedScreen.style.display = 'block';
    }
});