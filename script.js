// ============ CONSTANTS ============
const GAME_MODES = {
  AI_EASY: 'easy',
  AI_MEDIUM: 'medium',
  AI_HARD: 'hard',
  ONLINE: 'online'
};

const POINTS = {
  AI_EASY: 20,
  AI_MEDIUM: 35,
  AI_HARD: 60,
  ONLINE_WIN: 50,
  ONLINE_DRAW: 15
};

// ============ STATE ============
let appState = {
  currentUser: null,
  currentScreen: 'auth',
  gameMode: null,
  gameBoard: ['', '', '', '', '', '', '', '', ''],
  currentPlayer: 'x',
  gameActive: false,
  scores: { wins: 0, draws: 0, losses: 0 },
  roomCode: null,
  isOnlineGame: false,
  onlineOpponent: null
};

// ============ UI MANAGEMENT ============
function goScreen(screenName) {
  const screens = document.querySelectorAll('.screen');
  screens.forEach(s => s.classList.remove('active'));
  
  const targetScreen = document.getElementById(`screen-${screenName}`);
  if (targetScreen) {
    targetScreen.classList.add('active');
    appState.currentScreen = screenName;
    window.scrollTo(0, 0);
  }
}

// ============ AUTHENTICATION ============
function switchAuthTab(tab) {
  const tabs = document.querySelectorAll('.auth-tab');
  const forms = ['login-form', 'register-form', 'forgot-form'];
  
  tabs.forEach(t => t.classList.remove('active'));
  forms.forEach(f => document.getElementById(f)?.classList.add('hidden'));
  
  event.target.classList.add('active');
  document.getElementById(`${tab}-form`)?.classList.remove('hidden');
}

function doLogin() {
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;
  
  if (!email || !password) {
    showError('الرجاء ملء جميع الحقول');
    return;
  }
  
  if (!isValidEmail(email)) {
    showError('البريد الإلكتروني غير صحيح');
    return;
  }
  
  // Simulate login
  appState.currentUser = { email, username: email.split('@')[0], points: 1500 };
  loginSuccess();
}

function doRegister() {
  const name = document.getElementById('reg-name').value;
  const email = document.getElementById('reg-email').value;
  const password = document.getElementById('reg-password').value;
  
  if (!name || !email || !password) {
    showError('الرجاء ملء جميع الحقول');
    return;
  }
  
  if (!isValidEmail(email)) {
    showError('البريد الإلكتروني غير صحيح');
    return;
  }
  
  if (password.length < 6) {
    showError('كلمة السر يجب أن تكون 6 أحرف على الأقل');
    return;
  }
  
  appState.currentUser = { email, username: name, points: 0 };
  showSuccess('تم إنشاء الحساب بنجاح');
  setTimeout(loginSuccess, 1500);
}

function doForgot() {
  const email = document.getElementById('forgot-email').value;
  
  if (!email || !isValidEmail(email)) {
    showError('الرجاء إدخال بريد إلكتروني صحيح');
    return;
  }
  
  showSuccess('تم إرسال كود التحقق إلى بريدك');
  document.getElementById('reset-fields').classList.remove('hidden');
}

function doReset() {
  const code = document.getElementById('reset-code').value;
  const newPassword = document.getElementById('reset-password').value;
  
  if (!code || code.length !== 6) {
    showError('الرجاء إدخال كود تحقق صحيح');
    return;
  }
  
  if (newPassword.length < 6) {
    showError('كلمة السر يجب أن تكون 6 أحرف على الأقل');
    return;
  }
  
  showSuccess('تم تغيير كلمة السر بنجاح');
  setTimeout(() => switchAuthTab('login'), 1500);
}

function playAsGuest() {
  appState.currentUser = { email: 'guest@game.local', username: 'ضيف', points: 0, isGuest: true };
  loginSuccess();
}

function loginSuccess() {
  updateMenuUI();
  goScreen('menu');
}

function logout() {
  if (confirm('هل تريد تسجيل الخروج؟')) {
    appState.currentUser = null;
    appState.scores = { wins: 0, draws: 0, losses: 0 };
    goScreen('auth');
  }
}

// ============ MENU ============
function updateMenuUI() {
  if (!appState.currentUser) return;
  
  const firstLetter = appState.currentUser.username.charAt(0).toUpperCase();
  document.getElementById('menu-avatar').textContent = firstLetter;
  document.getElementById('menu-username').textContent = appState.currentUser.username;
  document.getElementById('menu-email').textContent = appState.currentUser.email;
  document.getElementById('menu-points').textContent = appState.currentUser.points;
  document.getElementById('store-points').textContent = appState.currentUser.points;
}

// ============ AI GAME ============
function startAI(difficulty) {
  appState.gameMode = difficulty;
  appState.gameBoard = ['', '', '', '', '', '', '', '', ''];
  appState.currentPlayer = 'x';
  appState.gameActive = true;
  appState.isOnlineGame = false;
  
  renderGameBoard();
  goScreen('game');
  updateScoreDisplay();
}

function renderGameBoard() {
  const board = document.getElementById('game-board');
  board.innerHTML = '';
  
  appState.gameBoard.forEach((cell, index) => {
    const cellEl = document.createElement('div');
    cellEl.className = `game-cell ${cell ? 'taken ' + cell : ''}`;
    
    if (cell === 'x') {
      cellEl.innerHTML = '<div class="mark"><svg viewBox="0 0 100 100"><line x1="20" y1="20" x2="80" y2="80"/><line x1="80" y1="20" x2="20" y2="80"/></svg></div>';
    } else if (cell === 'o') {
      cellEl.innerHTML = '<div class="mark"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="30"/></svg></div>';
    }
    
    if (!cell && appState.gameActive && appState.currentPlayer === 'x') {
      cellEl.style.cursor = 'pointer';
      cellEl.onclick = () => playMove(index);
    }
    
    board.appendChild(cellEl);
  });
}

function playMove(index) {
  if (appState.gameBoard[index] || !appState.gameActive || appState.currentPlayer !== 'x') return;
  
  appState.gameBoard[index] = 'x';
  checkGameStatus();
  
  if (appState.gameActive) {
    setTimeout(() => aiMove(), 500);
  }
  
  renderGameBoard();
}

function aiMove() {
  const availableMoves = appState.gameBoard
    .map((cell, i) => cell === '' ? i : null)
    .filter(i => i !== null);
  
  if (availableMoves.length === 0) return;
  
  let move;
  const difficulty = appState.gameMode;
  
  if (difficulty === 'easy') {
    move = availableMoves[Math.floor(Math.random() * availableMoves.length)];
  } else if (difficulty === 'medium') {
    move = Math.random() > 0.5 ? getBestMove() : availableMoves[Math.floor(Math.random() * availableMoves.length)];
  } else {
    move = getBestMove();
  }
  
  appState.gameBoard[move] = 'o';
  checkGameStatus();
  renderGameBoard();
}

function getBestMove() {
  // Simple minimax-like logic for AI
  const availableMoves = appState.gameBoard
    .map((cell, i) => cell === '' ? i : null)
    .filter(i => i !== null);
  
  // Check if can win
  for (let move of availableMoves) {
    const testBoard = [...appState.gameBoard];
    testBoard[move] = 'o';
    if (checkWinner(testBoard) === 'o') return move;
  }
  
  // Check if need to block
  for (let move of availableMoves) {
    const testBoard = [...appState.gameBoard];
    testBoard[move] = 'x';
    if (checkWinner(testBoard) === 'x') return move;
  }
  
  // Take center if available
  if (availableMoves.includes(4)) return 4;
  
  // Take corners
  const corners = [0, 2, 6, 8].filter(i => availableMoves.includes(i));
  if (corners.length > 0) return corners[Math.floor(Math.random() * corners.length)];
  
  return availableMoves[0];
}

function checkGameStatus() {
  const winner = checkWinner(appState.gameBoard);
  
  if (winner) {
    appState.gameActive = false;
    
    if (winner === 'x') {
      appState.scores.wins++;
      const points = POINTS[`AI_${appState.gameMode.toUpperCase()}`];
      appState.currentUser.points += points;
      showSuccess(`🎉 انتصرت! +${points} نقطة`);
    } else {
      appState.scores.losses++;
      showError('😢 خسرت المبارية');
    }
    
    updateScoreDisplay();
  } else if (appState.gameBoard.every(cell => cell)) {
    appState.gameActive = false;
    appState.scores.draws++;
    showSuccess('🤝 تعادل');
    updateScoreDisplay();
  } else {
    appState.currentPlayer = appState.currentPlayer === 'x' ? 'o' : 'x';
  }
}

function checkWinner(board) {
  const winConditions = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8], // Rows
    [0, 3, 6], [1, 4, 7], [2, 5, 8], // Columns
    [0, 4, 8], [2, 4, 6] // Diagonals
  ];
  
  for (let condition of winConditions) {
    const [a, b, c] = condition;
    if (board[a] && board[a] === board[b] && board[a] === board[c]) {
      return board[a];
    }
  }
  
  return null;
}

function updateScoreDisplay() {
  document.getElementById('score-win').textContent = appState.scores.wins;
  document.getElementById('score-draw').textContent = appState.scores.draws;
  document.getElementById('score-loss').textContent = appState.scores.losses;
}

function newRound() {
  startAI(appState.gameMode);
}

function quitGame() {
  if (confirm('هل تريد الخروج من اللعبة؟')) {
    goScreen('menu');
  }
}

// ============ ONLINE GAME ============
function createRoom(isParty) {
  const code = generateRoomCode();
  appState.roomCode = code;
  appState.isOnlineGame = true;
  
  document.getElementById('online-start').classList.add('hidden');
  document.getElementById('online-room').classList.remove('hidden');
  document.getElementById('room-code').textContent = code;
}

function generateRoomCode() {
  return Math.random().toString(36).substring(2, 8).toUpperCase();
}

function showJoinForm() {
  document.getElementById('online-start').classList.add('hidden');
  document.getElementById('online-join').classList.remove('hidden');
}

function goOnlineStart() {
  document.getElementById('online-join').classList.add('hidden');
  document.getElementById('online-start').classList.remove('hidden');
}

function joinRoom(asSpectator) {
  const code = document.getElementById('join-code-input').value.toUpperCase();
  
  if (!code || code.length !== 6) {
    showError('الرجاء إدخال كود غرفة صحيح');
    return;
  }
  
  appState.roomCode = code;
  appState.isOnlineGame = true;
  
  document.getElementById('online-start').classList.add('hidden');
  document.getElementById('online-join').classList.add('hidden');
  document.getElementById('online-room').classList.remove('hidden');
  document.getElementById('room-code').textContent = code;
  
  showSuccess(asSpectator ? 'تم الانضمام كمشاهد' : 'تم الانضمام كلاعب');
}

function copyRoomCode() {
  const code = document.getElementById('room-code').textContent;
  navigator.clipboard.writeText(code).then(() => {
    showSuccess('تم نسخ الكود');
  });
}

function leaveRoom() {
  if (confirm('هل تريد الخروج من الغرفة؟')) {
    document.getElementById('online-room').classList.add('hidden');
    document.getElementById('online-start').classList.remove('hidden');
    appState.roomCode = null;
    appState.isOnlineGame = false;
  }
}

function sendRoomChat() {
  const input = document.getElementById('room-chat-input');
  const message = input.value.trim();
  
  if (!message) return;
  
  const messagesDiv = document.getElementById('room-chat-messages');
  const msgEl = document.createElement('div');
  msgEl.className = 'chat-message own';
  msgEl.innerHTML = `<span class="time">${new Date().toLocaleTimeString('ar-SA')}</span><span class="author">${appState.currentUser.username}</span>: ${escapeHtml(message)}`;
  
  messagesDiv.appendChild(msgEl);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
  input.value = '';
}

function sendGlobalChat() {
  const input = document.getElementById('global-chat-input');
  const message = input.value.trim();
  
  if (!message) return;
  
  const messagesDiv = document.getElementById('global-chat-messages');
  const msgEl = document.createElement('div');
  msgEl.className = 'chat-message own';
  msgEl.innerHTML = `<span class="time">${new Date().toLocaleTimeString('ar-SA')}</span><span class="author">${appState.currentUser.username}</span>: ${escapeHtml(message)}`;
  
  messagesDiv.appendChild(msgEl);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
  input.value = '';
}

function restartOnline() {
  appState.gameBoard = ['', '', '', '', '', '', '', '', ''];
  appState.currentPlayer = 'x';
  appState.gameActive = true;
  renderGameBoard();
}

// ============ PROFILE & LEADERBOARD ============
function loadProfile() {
  const profile = document.getElementById('profile-content');
  profile.innerHTML = `
    <div class="profile-header">
      <div class="profile-avatar-big">${appState.currentUser.username.charAt(0).toUpperCase()}</div>
      <div class="profile-name">${appState.currentUser.username}</div>
      <div class="profile-email">${appState.currentUser.email}</div>
      <div class="profile-stats-grid">
        <div class="profile-stat w">
          <div class="v">${appState.scores.wins}</div>
          <div class="l">WINS</div>
        </div>
        <div class="profile-stat l">
          <div class="v">${appState.scores.losses}</div>
          <div class="l">LOSSES</div>
        </div>
        <div class="profile-stat d">
          <div class="v">${appState.scores.draws}</div>
          <div class="l">DRAWS</div>
        </div>
      </div>
    </div>
  `;
}

function loadLeaderboard() {
  const list = document.getElementById('leaderboard-list');
  const mockData = [
    { rank: 1, name: 'أحمد', points: 2500 },
    { rank: 2, name: 'فاطمة', points: 2100 },
    { rank: 3, name: 'محمد', points: 1850 }
  ];
  
  list.innerHTML = mockData.map(user => `
    <div class="lb-item rank-${user.rank}">
      <div class="lb-rank">${user.rank}</div>
      <div class="lb-info">
        <div class="lb-name">${user.name}</div>
        <div class="lb-sub">اللاعب #${user.rank}</div>
      </div>
      <div class="lb-points">${user.points}</div>
    </div>
  `).join('');
}

function loadHistory() {
  const list = document.getElementById('history-list');
  const mockHistory = [
    { mode: 'AI Hard', result: 'win', date: 'اليوم', time: '14:30' },
    { mode: 'AI Medium', result: 'loss', date: 'أمس', time: '19:45' }
  ];
  
  list.innerHTML = mockHistory.map(match => `
    <div class="match-item">
      <div class="match-result ${match.result}">${match.result === 'win' ? '✓' : '✗'}</div>
      <div class="match-info">
        <div class="match-mode">${match.mode}</div>
        <div class="match-date">${match.date} - ${match.time}</div>
      </div>
      <div class="match-status ${match.result}">${match.result === 'win' ? 'فوز' : 'خسارة'}</div>
    </div>
  `).join('');
}

function loadParties() {
  showSuccess('جاري تحميل الحفلات...');
}

// ============ NOTIFICATIONS ============
function showError(message) {
  const errorEl = document.getElementById('auth-error');
  if (errorEl) {
    errorEl.textContent = message;
    errorEl.classList.add('show');
    setTimeout(() => errorEl.classList.remove('show'), 4000);
  }
  showToast(message, 'error');
}

function showSuccess(message) {
  const successEl = document.getElementById('auth-success');
  if (successEl) {
    successEl.textContent = message;
    successEl.classList.add('show');
    setTimeout(() => successEl.classList.remove('show'), 4000);
  }
  showToast(message, 'success');
}

function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `show ${type}`;
  
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

// ============ UTILITIES ============
function isValidEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function showLoading(show = true) {
  const loader = document.getElementById('loading-overlay');
  if (show) {
    loader.classList.add('show');
  } else {
    loader.classList.remove('show');
  }
}

// ============ CONNECTION STATUS ============
function updateConnectionStatus(isOnline = true) {
  const indicator = document.getElementById('conn-indicator');
  if (isOnline) {
    indicator.classList.add('show');
    indicator.classList.remove('offline');
  } else {
    indicator.classList.add('show', 'offline');
  }
}

window.addEventListener('online', () => updateConnectionStatus(true));
window.addEventListener('offline', () => updateConnectionStatus(false));

// ============ EVENT LISTENERS ============
document.addEventListener('DOMContentLoaded', () => {
  updateConnectionStatus(navigator.onLine);
  
  // Initialize
  document.getElementById('screen-auth').classList.add('active');
  
  // Prevent double tap zoom
  document.addEventListener('touchstart', function(event) {
    if (event.touches.length > 1) {
      event.preventDefault();
    }
  });
});

// Handle keyboard navigation
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    // Can add escape key handling here
  }
});

// ============ EXPORTS (if needed for modular usage) ============
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { appState, goScreen, startAI, createRoom, joinRoom };
}
