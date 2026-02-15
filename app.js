const rows = 10, cols = 17, cell = 40;
const boardX = 20, boardY = 25;
const timerBarX = boardX + cols * cell + 12, timerBarY = boardY + 20, timerBarW = 18, timerBarH = rows * cell - 40;

const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const scoreEl = document.getElementById('score');
const timeEl = document.getElementById('time');
const rankBody = document.getElementById('rankBody');
const overlay = document.getElementById('startOverlay');
const bgm = document.getElementById('bgm');

let grid = [];
let score = 0;
let timeLeft = 120;
let started = false;
let paused = false;
let timerId = null;
let dragStart = null;
let dragNow = null;
let lightMode = true;
let activePointerId = null;

function rand1to9() { return Math.floor(Math.random() * 9) + 1; }
function initGrid() { grid = Array.from({ length: rows }, () => Array.from({ length: cols }, rand1to9)); }
function toCell(mx, my) {
  const c = Math.floor((mx - boardX) / cell), r = Math.floor((my - boardY) / cell);
  if (r < 0 || c < 0 || r >= rows || c >= cols) return null;
  return [r, c];
}
function selRange() {
  if (!dragStart || !dragNow) return null;
  const [sr, sc] = dragStart, [er, ec] = dragNow;
  return [Math.min(sr, er), Math.max(sr, er), Math.min(sc, ec), Math.max(sc, ec)];
}
function sumAndCells() {
  const rg = selRange(); if (!rg) return { sum: 0, cells: [] };
  const [r1, r2, c1, c2] = rg;
  let sum = 0, cells = [];
  for (let r = r1; r <= r2; r++) for (let c = c1; c <= c2; c++) if (grid[r][c] != null) { sum += grid[r][c]; cells.push([r, c]); }
  return { sum, cells };
}
function hasPossibleTen() {
  for (let r1 = 0; r1 < rows; r1++) for (let r2 = r1; r2 < rows; r2++) for (let c1 = 0; c1 < cols; c1++) {
    let colSums = new Array(cols).fill(0);
    for (let c = c1; c < cols; c++) {
      let s = 0;
      for (let r = r1; r <= r2; r++) s += (grid[r][c] ?? 0);
      colSums[c] = s;
      let acc = 0;
      for (let k = c1; k <= c; k++) acc += colSums[k];
      if (acc === 10) return true;
    }
  }
  return false;
}

function drawApple(x, y, v) {
  const m = 6, x1 = x + m, y1 = y + m, x2 = x + cell - m, y2 = y + cell - m;
  ctx.fillStyle = lightMode ? '#ff4a3d' : '#ef3f33';
  ctx.strokeStyle = lightMode ? '#e73a2e' : '#cc3027';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.ellipse((x1+x2)/2, (y1+y2)/2, (x2-x1)/2, (y2-y1)/2, 0, 0, Math.PI*2); ctx.fill(); ctx.stroke();

  ctx.fillStyle = '#de3228';
  ctx.beginPath(); ctx.ellipse((x1+x2)/2, y2-6, (x2-x1)/2-2, 7, 0, 0, Math.PI); ctx.fill();

  ctx.strokeStyle = '#6b3f1f'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo((x1+x2)/2, y1+2); ctx.lineTo((x1+x2)/2-1, y1-5); ctx.stroke();
  ctx.fillStyle = '#3ddb99'; ctx.strokeStyle = '#14ad74'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.ellipse((x1+x2)/2+8, y1-3, 6, 4, 0, 0, Math.PI*2); ctx.fill(); ctx.stroke();

  const tx = (x1+x2)/2, ty = (y1+y2)/2 + 2;
  ctx.font = 'bold 20px Arial';
  ctx.fillStyle = '#cf3f0a';
  for (const [ox, oy] of [[-1,0],[1,0],[0,-1],[0,1],[-1,-1],[1,-1],[-1,1],[1,1]]) ctx.fillText(String(v), tx-6+ox, ty+oy);
  ctx.fillStyle = 'white'; ctx.fillText(String(v), tx-6, ty);
}

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#b7efc5'; ctx.fillRect(0,0,canvas.width,canvas.height);
  for (let r=0;r<rows;r++) for (let c=0;c<cols;c++) {
    const x = boardX + c*cell, y = boardY + r*cell;
    ctx.fillStyle = (r+c)%2===0 ? '#d8f8df' : '#cbf3d3';
    ctx.fillRect(x,y,cell,cell);
    ctx.strokeStyle = '#d8f7d8'; ctx.strokeRect(x,y,cell,cell);
    if (grid[r][c] != null) drawApple(x,y,grid[r][c]);
  }

  if (dragStart && dragNow) {
    const [r1,r2,c1,c2] = selRange();
    ctx.strokeStyle = '#38bdf8'; ctx.lineWidth = 2;
    for (let r=r1;r<=r2;r++) for (let c=c1;c<=c2;c++) ctx.strokeRect(boardX+c*cell+1, boardY+r*cell+1, cell-2, cell-2);
    ctx.lineWidth = 3;
    ctx.strokeRect(boardX + c1*cell+2, boardY + r1*cell+2, (c2-c1+1)*cell-4, (r2-r1+1)*cell-4);
  }

  const ratio = timeLeft / 120;
  const fillH = Math.max(0, Math.floor((timerBarH-6) * ratio));
  ctx.fillStyle = '#ecfdf3'; ctx.fillRect(timerBarX, timerBarY, timerBarW, timerBarH);
  ctx.strokeStyle = '#16a34a'; ctx.strokeRect(timerBarX, timerBarY, timerBarW, timerBarH);
  let tColor = '#18c839'; if (ratio <= .5) tColor = '#f2b51d'; if (ratio <= .25) tColor = '#f04a2f';
  ctx.fillStyle = tColor; ctx.fillRect(timerBarX+3, timerBarY + timerBarH - 3 - fillH, timerBarW-6, fillH);

  scoreEl.textContent = `SCORE ${score}`;
  timeEl.textContent = String(timeLeft);
  timeEl.style.color = tColor;
}

function endGame(reason) {
  started = false;
  clearInterval(timerId);
  timerId = null;
  bgm.pause(); bgm.currentTime = 0;
  const name = prompt(`게임 종료: ${reason}\n점수 ${score}점 기록 이름 입력`, 'Player');
  if (name !== null) {
    const key = 'apple_rankings';
    const arr = JSON.parse(localStorage.getItem(key) || '[]');
    arr.push({ name: (name.trim() || 'Player').slice(0, 20), score, time: new Date().toISOString() });
    arr.sort((a,b)=>b.score-a.score);
    localStorage.setItem(key, JSON.stringify(arr.slice(0,10)));
    renderRanks();
  }
  overlay.style.display = 'flex';
  overlay.textContent = 'START 버튼을 눌러 시작';
}

function tick() {
  if (!started || paused) return;
  timeLeft = Math.max(0, timeLeft - 1);
  if (timeLeft === 0) endGame('시간 종료');
  draw();
}

function resetBoard() {
  initGrid(); score = 0; timeLeft = 120; dragStart = dragNow = null; draw();
}

function startGame() {
  started = true; paused = false; resetBoard();
  overlay.style.display = 'none';
  if (document.getElementById('bgmToggle').checked) bgm.play().catch(()=>{});
  clearInterval(timerId); timerId = setInterval(tick, 1000);
}

canvas.addEventListener('pointerdown', (e) => {
  if (!started || paused) return;
  activePointerId = e.pointerId;
  canvas.setPointerCapture(e.pointerId);
  dragStart = toCell(e.offsetX, e.offsetY);
  dragNow = dragStart;
  draw();
});

canvas.addEventListener('pointermove', (e) => {
  if (!dragStart || !started || paused) return;
  if (activePointerId !== e.pointerId) return;
  const c = toCell(e.offsetX, e.offsetY);
  if (c) {
    dragNow = c;
    draw();
  }
});

function finalizeSelection(e) {
  if (!dragStart || !started || paused) return;
  if (activePointerId !== e.pointerId) return;
  const c = toCell(e.offsetX, e.offsetY);
  if (c) dragNow = c;
  const { sum, cells } = sumAndCells();
  if (cells.length && sum === 10) {
    for (const [r, cc] of cells) grid[r][cc] = null;
    score += 10;
    if (!hasPossibleTen()) endGame('더 이상 10을 만들 수 없음');
  }
  dragStart = dragNow = null; draw();
  activePointerId = null;
}

canvas.addEventListener('pointerup', finalizeSelection);
canvas.addEventListener('pointercancel', (e) => {
  if (activePointerId !== e.pointerId) return;
  dragStart = dragNow = null;
  activePointerId = null;
  draw();
});

document.getElementById('startBtn').onclick = startGame;
document.getElementById('resetBtn').onclick = () => { if (started) resetBoard(); };
document.getElementById('pauseBtn').onclick = () => {
  if (!started) return;
  paused = !paused;
  document.getElementById('pauseBtn').textContent = paused ? '재개' : '일시정지';
  if (paused) {
    bgm.pause();
    overlay.style.display = 'flex';
    overlay.textContent = '일시정지';
  } else {
    overlay.style.display = 'none';
    if (document.getElementById('bgmToggle').checked) bgm.play().catch(()=>{});
  }
};

document.getElementById('lightToggle').onchange = (e) => { lightMode = e.target.checked; draw(); };
document.getElementById('bgmToggle').onchange = (e) => {
  if (!started) return;
  if (e.target.checked) bgm.play().catch(()=>{});
  else bgm.pause();
};

function renderRanks() {
  const arr = JSON.parse(localStorage.getItem('apple_rankings') || '[]');
  rankBody.innerHTML = '';
  if (!arr.length) {
    rankBody.innerHTML = '<tr><td>-</td><td>기록 없음</td><td>-</td></tr>';
    return;
  }
  arr.slice(0,10).forEach((it, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i+1}</td><td>${it.name}</td><td>${it.score}</td>`;
    rankBody.appendChild(tr);
  });
}

resetBoard();
renderRanks();
