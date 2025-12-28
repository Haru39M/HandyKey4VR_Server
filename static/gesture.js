document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-btn');
    const configSection = document.getElementById('config-section');
    const testSection = document.getElementById('test-section');
    const finishedScreen = document.getElementById('finished-screen');
    
    const targetImg = document.getElementById('target-img');
    const targetName = document.getElementById('target-name');
    const targetDesc = document.getElementById('target-desc');
    const matchIndicator = document.getElementById('match-indicator');
    const progressText = document.getElementById('progress-text');
    
    const overlay = document.getElementById('overlay-message');
    const overlayText = document.getElementById('overlay-text');

    const fingerIds = ['T', 'I', 'M', 'R', 'P'];
    let pollingInterval = null;

    startBtn.addEventListener('click', async () => {
        const pid = document.getElementById('participant-id').value;
        const cond = document.getElementById('condition').value;
        const maxTrials = document.getElementById('max-trials').value;

        try {
            await fetch('/gesture/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    participant_id: pid,
                    condition: cond,
                    max_trials: maxTrials
                })
            });

            configSection.style.display = 'none';
            testSection.style.display = 'block';
            
            if (pollingInterval) clearInterval(pollingInterval);
            pollingInterval = setInterval(updateState, 100);

        } catch (e) {
            console.error(e);
            alert("Error starting test");
        }
    });

    async function updateState() {
        try {
            const res = await fetch('/gesture/state');
            const data = await res.json();

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
                
                // サーバーから送られてきた残り時間を使用 (小数点切り上げ)
                // data.countdown_remaining は float (例: 2.34...)
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
                    targetImg.src = `/gesture_images/${imgName}`;
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

    function finishTest() {
        clearInterval(pollingInterval);
        testSection.style.display = 'none';
        finishedScreen.style.display = 'block';
    }
});