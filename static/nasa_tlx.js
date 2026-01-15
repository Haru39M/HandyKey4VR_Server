function startSurvey() {
    document.getElementById('startBtn').style.display = 'none';
    document.getElementById('block1').classList.add('active');
}

function unlockNext(nextId) {
    const nextBlock = document.getElementById('block' + nextId);
    if (nextBlock) nextBlock.classList.add('active');
}

function enableSubmit() {
    const btn = document.getElementById('submitBtn');
    btn.disabled = false;
    btn.textContent = "回答を終了して保存する";
    btn.style.backgroundColor = "#28a745"; // 緑色に変更
}

// 数値を更新する関数
function updateValue(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = value;
    }
}