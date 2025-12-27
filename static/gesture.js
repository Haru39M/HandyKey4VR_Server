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

    const fingerIds = ['T', 'I', 'M', 'R', 'P'];
    let pollingInterval = null;

    // テスト開始
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
            
            // ポーリング開始 (100ms間隔 = 10fps)
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

            if (!data.is_running) {
                if (data.is_completed) {
                    finishTest();
                }
                return;
            }

            // ターゲット表示更新
            if (data.target) {
                // 画像パスの調整: "gesture_images/" はFlaskのルートで解決
                // JSONに "Image": "Thumbs.jpg" のようにあればそれを使う
                // なければ "gesture_neutral.png" のようなデフォルト名を生成するか、jsonの仕様に合わせる
                // ここでは jsonにImageフィールドがある場合とない場合を考慮
                let imgName = data.target.Image;
                if (!imgName) {
                    // フォールバック: GestureNameからファイル名を推測
                    // 例: "Fist" -> "gesture_fist.png"
                    imgName = `gesture_${data.target.GestureName.toLowerCase()}.png`;
                }
                
                targetImg.src = `/gesture_images/${imgName}`;
                targetName.textContent = data.target.GestureName;
                targetDesc.textContent = data.target.Description || "";
                
                // 定義状態のヒントを表示したければここに追加
            }

            // 現在の手の状態更新
            if (data.current_input) {
                fingerIds.forEach(fid => {
                    const el = document.querySelector(`#f-${fid} .f-val`);
                    const val = data.current_input[fid];
                    el.textContent = val;
                    
                    // ターゲットの状態と合致しているか色付けすると親切（オプション）
                });
            }

            // 判定結果更新
            if (data.is_match) {
                matchIndicator.textContent = "MATCH";
                matchIndicator.className = "indicator match";
            } else {
                matchIndicator.textContent = "WAIT...";
                matchIndicator.className = "indicator mismatch";
            }

            // 進捗更新
            if (data.progress) {
                progressText.textContent = data.progress;
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