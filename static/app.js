/* ==========================================================================
   Взаємодія — клієнт
   Один екран = одна функція view*(). Стан тримається в S, розмітка
   збирається рядками, всі дані з бекенду екрануються через esc().
   ========================================================================== */

const S = {
  token: localStorage.getItem('vz_token') || null,
  user: null,
  meta: null,
  overview: null,
  view: 'board',
  filters: { category: null, urgency: null, q: '' },
};

const $ = (id) => document.getElementById(id);
const gate = $('gate');
const app = $('app');
const rail = $('rail');
const main = $('main');
const modalRoot = $('modal-root');

/* ---------- дрібні помічники ---------- */

function esc(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

const money = (n) => new Intl.NumberFormat('uk-UA').format(Math.round(n || 0));

function initials(user) {
  if (!user) return '—';
  return ((user.first_name || '?')[0] + (user.last_name || '')[0] || '').toUpperCase();
}

function nameOf(user) {
  if (!user) return 'Невідомо';
  const base = `${user.first_name || ''} ${user.last_name || ''}`.trim();
  return user.callsign ? `${base} «${user.callsign}»` : base;
}

function when(iso) {
  const then = new Date(iso);
  const mins = Math.floor((Date.now() - then.getTime()) / 60000);
  if (mins < 1) return 'щойно';
  if (mins < 60) return `${mins} хв тому`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} год тому`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'учора';
  if (days < 7) return `${days} дн тому`;
  return then.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' });
}

function label(group, value) {
  const list = (S.meta && S.meta[group]) || [];
  const found = list.find((o) => o.value === value);
  return found ? found.label : value;
}

const mark = (category) => (S.meta && S.meta.category_marks[category]) || '—';

function toast(message, bad = false) {
  const node = document.createElement('div');
  node.className = 'toast' + (bad ? ' bad' : '');
  node.textContent = message;
  $('toasts').appendChild(node);
  setTimeout(() => node.remove(), 3600);
}

/* ---------- звернення до API ---------- */

async function api(path, { method = 'GET', body, quiet = false } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (S.token) headers.Authorization = `Bearer ${S.token}`;

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 401 && S.token) {
    signOut();
    throw new Error('Сесія завершилась');
  }

  let payload = null;
  try { payload = await response.json(); } catch { /* порожня відповідь */ }

  if (!response.ok) {
    const message = readError(payload) || 'Щось пішло не так. Спробуйте ще раз.';
    if (!quiet) toast(message, true);
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function readError(payload) {
  if (!payload) return null;
  const detail = payload.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : '';
    return `Перевірте поле «${field}»: ${first.msg}`;
  }
  return null;
}

/* ---------- вхід ---------- */

const DEMO_LINE = 'Демо-акаунти: <code>kovalenko</code> (військовий), <code>marchenko</code> (волонтер), <code>lysenko</code> (цивільний). Пароль у всіх — <code>demo1234</code>.';

function viewGate(mode = 'login') {
  app.hidden = true;
  gate.hidden = false;

  const isLogin = mode === 'login';
  gate.innerHTML = `
    <aside class="gate-art">
      <div>
        <span class="brand-mark">Взаємодія</span>
        <span class="brand-sub">дошка запитів</span>
      </div>
      <p class="gate-claim">Запит бачать <b>усі</b>, хто може його закрити.</p>
      <div class="gate-legend">
        <div><span>ЗАПИТ</span>Військовий публікує потребу — з категорією, кількістю і пріоритетом.</div>
        <div><span>РОБОТА</span>Волонтер бере запит на себе, і той зникає з вільної дошки.</div>
        <div><span>ЗВІТ</span>Закриття підтверджує автор запиту, а не виконавець.</div>
      </div>
    </aside>
    <section class="gate-form">
      <div class="gate-form-inner">
        <div class="head">
          <span class="eyebrow">${isLogin ? 'вхід' : 'реєстрація'}</span>
          <h1>${isLogin ? 'З поверненням' : 'Створити акаунт'}</h1>
        </div>
        <form id="gate-form">
          ${isLogin ? '' : `
            <div class="field-row">
              <div class="field"><label for="g-first">Імʼя</label><input id="g-first" required maxlength="64"></div>
              <div class="field"><label for="g-last">Прізвище</label><input id="g-last" required maxlength="64"></div>
            </div>
            <div class="field">
              <label for="g-role">Роль</label>
              <select id="g-role">
                <option value="military">Військовий — публікує запити</option>
                <option value="volunteer">Волонтер — бере запити в роботу</option>
                <option value="civilian">Цивільна особа — донатить і підтримує збори</option>
              </select>
            </div>
            <div class="field-row">
              <div class="field"><label for="g-callsign">Позивний</label><input id="g-callsign" maxlength="48" placeholder="не обовʼязково"></div>
              <div class="field"><label for="g-contact">Контакт</label><input id="g-contact" maxlength="120" placeholder="@нік або телефон"></div>
            </div>
          `}
          <div class="field"><label for="g-username">Імʼя користувача</label><input id="g-username" required minlength="3" maxlength="48" autocomplete="username"></div>
          <div class="field"><label for="g-password">Пароль</label><input id="g-password" type="password" required minlength="6" autocomplete="${isLogin ? 'current-password' : 'new-password'}"></div>
          <button class="btn wide" type="submit">${isLogin ? 'Увійти' : 'Зареєструватись'}</button>
        </form>
        <p class="gate-switch">
          ${isLogin ? 'Ще немає акаунту?' : 'Уже маєте акаунт?'}
          <a href="#" id="gate-switch">${isLogin ? 'Зареєструватись' : 'Увійти'}</a>
        </p>
        ${isLogin ? `<p class="gate-demo">${DEMO_LINE}</p>` : ''}
      </div>
    </section>
  `;

  $('gate-switch').onclick = (event) => { event.preventDefault(); viewGate(isLogin ? 'register' : 'login'); };
  $('gate-form').onsubmit = async (event) => {
    event.preventDefault();
    const button = event.target.querySelector('button');
    button.disabled = true;
    try {
      const body = {
        username: $('g-username').value.trim(),
        password: $('g-password').value,
      };
      if (!isLogin) {
        Object.assign(body, {
          first_name: $('g-first').value.trim(),
          last_name: $('g-last').value.trim(),
          role: $('g-role').value,
          callsign: $('g-callsign').value.trim() || null,
          contact: $('g-contact').value.trim() || null,
        });
      }
      const data = await api(isLogin ? '/auth/login' : '/auth/register', { method: 'POST', body });
      S.token = data.access_token;
      S.user = data.user;
      localStorage.setItem('vz_token', S.token);
      await boot();
    } catch { /* повідомлення вже показане */ } finally {
      button.disabled = false;
    }
  };
}

function signOut() {
  delete document.documentElement.dataset.role;
  S.token = null;
  S.user = null;
  localStorage.removeItem('vz_token');
  location.hash = '';
  viewGate('login');
}

/* ---------- каркас ---------- */

/* Кожна роль дістає свій набір розділів і свою назву для них.
   Волонтер працює з чергою, військовий веде реєстр, цивільний підтримує. */
const NAV = {
  military: [
    { id: 'ledger',    label: 'Журнал потреб' },
    { id: 'board',     label: 'Спільна дошка',  count: (o) => o.needs_open },
    { id: 'funds',     label: 'Збори',          count: (o) => o.funds_active },
    { id: 'donations', label: 'Склад донатів',  count: (o) => o.donations_available },
    { id: 'feed',      label: 'Хроніка' },
    { id: 'profile',   label: 'Профіль' },
  ],
  volunteer: [
    { id: 'board',     label: 'Дошка запитів',  count: (o) => o.needs_open },
    { id: 'assigned',  label: 'У мене в роботі' },
    { id: 'funds',     label: 'Збори',          count: (o) => o.funds_active },
    { id: 'donations', label: 'Донати речами',  count: (o) => o.donations_available },
    { id: 'feed',      label: 'Стрічка' },
    { id: 'leaders',   label: 'Дошка пошани' },
    { id: 'profile',   label: 'Профіль' },
  ],
  civilian: [
    { id: 'support',   label: 'Підтримати',        count: (o) => o.funds_active },
    { id: 'glance',    label: 'Що зараз потрібно', count: (o) => o.needs_open },
    { id: 'donations', label: 'Донати речами' },
    { id: 'feed',      label: 'Що відбувається' },
    { id: 'leaders',   label: 'Дошка пошани' },
    { id: 'profile',   label: 'Профіль' },
  ],
};

const HOME = { military: 'ledger', volunteer: 'board', civilian: 'support' };

const SUBTITLE = { military: 'журнал потреб', volunteer: 'дошка запитів', civilian: 'підтримка' };

function renderRail() {
  const overview = S.overview || {};
  const links = (NAV[S.user.role] || NAV.volunteer).map((item) => {
    const count = item.count ? item.count(overview) : null;
    return `<a class="rail-link ${S.view === item.id ? 'active' : ''}" href="#/${item.id}">
      ${esc(item.label)}${count ? `<span class="count">${count}</span>` : ''}
    </a>`;
  }).join('');

  rail.innerHTML = `
    <div class="brand">
      <span class="brand-mark">Взаємодія</span>
      <span class="brand-sub">${esc(SUBTITLE[S.user.role] || "")}</span>
    </div>
    <div class="rail-group">Розділи</div>
    ${links}
    <div class="rail-foot">
      <div class="rail-user">
        <div class="avatar">${esc(initials(S.user))}</div>
        <div class="who">
          <b>${esc(nameOf(S.user))}</b>
          <span>${esc(label('roles', S.user.role))}</span>
        </div>
      </div>
      <button class="btn ghost sm wide" style="margin-top:12px" id="sign-out">Вийти</button>
    </div>
  `;
  const out = $('sign-out');
  if (out) out.onclick = signOut;
}

function strip() {
  const o = S.overview;
  if (!o) return '';
  const cells = [
    ['Вільних запитів', o.needs_open, false],
    ['Критичних', o.needs_critical, o.needs_critical > 0],
    ['У роботі', o.needs_in_progress, false],
    ['Закрито', o.needs_completed, false],
    ['Зібрано, грн', money(o.funds_raised), false],
    ['Волонтерів', o.volunteers, false],
  ];
  return `<div class="strip">${cells.map(([lbl, num, alarm]) => `
    <div class="cell"><span class="num ${alarm ? 'alarm' : ''}">${esc(num)}</span><span class="lbl">${esc(lbl)}</span></div>
  `).join('')}</div>`;
}

/* ---------- екран: дошка запитів ---------- */

function needCard(need) {
  return `<button class="card urg-${esc(need.urgency)}" data-need="${esc(need.id)}">
    <div class="card-mark">
      <span class="urg-dot" title="${esc(label('urgencies', need.urgency))}"></span>
      <span class="mk">${esc(mark(need.category))}</span>
    </div>
    <div class="card-body">
      <div class="card-top">
        <span class="card-title">${esc(need.title)}</span>
        <span class="stamp ${esc(need.status)}">${esc(label('need_statuses', need.status))}</span>
      </div>
      <div class="card-desc">${esc(need.description)}</div>
      <div class="card-meta">
        <span><b>${esc(need.quantity)} ${esc(need.unit)}</b></span>
        <span>${esc(label('categories', need.category))}</span>
        <span>${esc(label('urgencies', need.urgency))}</span>
        <span>${esc(nameOf(need.author))}</span>
        ${need.assignee ? `<span>виконує <b>${esc(nameOf(need.assignee))}</b></span>` : ''}
        <span>${esc(when(need.created_at))}</span>
      </div>
    </div>
  </button>`;
}

function filterBar() {
  const cats = (S.meta.categories || []).map((c) =>
    `<button class="chip ${S.filters.category === c.value ? 'on' : ''}" data-cat="${esc(c.value)}">${esc(c.label)}</button>`
  ).join('');
  const urgs = (S.meta.urgencies || []).map((u) =>
    `<button class="chip ${S.filters.urgency === u.value ? 'on' : ''}" data-urg="${esc(u.value)}">${esc(u.label)}</button>`
  ).join('');
  return `<div class="filters">
    <input class="search" id="q" placeholder="Пошук за назвою або описом" value="${esc(S.filters.q)}">
    <button class="chip ${!S.filters.category && !S.filters.urgency ? 'on' : ''}" data-cat="">Усі</button>
    ${cats}
    <span style="width:100%"></span>
    ${urgs}
  </div>`;
}

function bindFilters(reload) {
  main.querySelectorAll('[data-cat]').forEach((node) => {
    node.onclick = () => {
      const value = node.dataset.cat;
      S.filters.category = value || null;
      if (!value) S.filters.urgency = null;
      reload();
    };
  });
  main.querySelectorAll('[data-urg]').forEach((node) => {
    node.onclick = () => {
      S.filters.urgency = S.filters.urgency === node.dataset.urg ? null : node.dataset.urg;
      reload();
    };
  });
  const search = $('q');
  if (search) {
    let timer;
    search.oninput = () => {
      clearTimeout(timer);
      timer = setTimeout(() => { S.filters.q = search.value; reload(); }, 280);
    };
  }
}

function bindCards() {
  main.querySelectorAll('[data-need]').forEach((node) => {
    node.onclick = () => openNeed(node.dataset.need);
  });
}

async function viewBoard(scope = 'all') {
  const titles = {
    all: ['дошка', 'Вільні запити', 'Усе, що зараз потребує рук. Критичні — зверху.'],
    mine: ['мої запити', 'Опубліковані мною', 'Стежте за станом і підтверджуйте виконання.'],
    assigned: ['у роботі', 'Узяті мною запити', 'Коли закриєте — надішліть на підтвердження автору.'],
  };
  const [eyebrow, title, lede] = titles[scope];
  const canCreate = S.user.role === 'military';

  main.innerHTML = `<div class="spinner">завантаження…</div>`;

  const params = new URLSearchParams({ scope });
  if (S.filters.category) params.set('category', S.filters.category);
  if (S.filters.urgency) params.set('urgency', S.filters.urgency);
  if (S.filters.q) params.set('q', S.filters.q);

  const needs = await api(`/needs?${params}`);

  const shift = scope === 'all' && S.user.role === 'volunteer'
    ? await api('/needs?scope=assigned', { quiet: true }).catch(() => [])
    : [];

  main.innerHTML = `
    <div class="head">
      <span class="eyebrow">${eyebrow}</span>
      <h1>${title}</h1>
      <p class="lede">${lede}</p>
    </div>
    ${scope === 'all' && S.user.role === 'volunteer' ? shiftBlock(shift) : ''}
    ${scope === 'all' ? strip() : ''}
    ${canCreate ? `<div style="margin-bottom:18px"><button class="btn accent" id="new-need">Створити запит</button></div>` : ''}
    ${filterBar()}
    <div class="cards">
      ${needs.length ? needs.map(needCard).join('') : emptyBoard(scope)}
    </div>
  `;

  bindFilters(() => viewBoard(scope));
  bindCards();
  const create = $('new-need');
  if (create) create.onclick = () => modalCreateNeed(() => viewBoard(scope));
}

function shiftBlock(items) {
  return `<section class="shift">
    <h2>У мене в роботі — ${items.length}</h2>
    ${items.length ? items.map((n) => `<div class="shift-row">
      <b>${esc(n.title)}</b>
      <span class="stamp ${esc(n.status)}">${esc(label('need_statuses', n.status))}</span>
      <button class="btn sm" data-need="${esc(n.id)}">Відкрити</button>
    </div>`).join('')
      : '<div class="shift-row shift-empty">Поки нічого. Оберіть запит нижче — він закріпиться за вами і зникне з вільної дошки.</div>'}
  </section>`;
}

function emptyBoard(scope) {
  const text = {
    all: ['Дошка порожня', 'Або всі запити вже розібрані, або фільтри надто вузькі.'],
    mine: ['Ви ще не публікували запитів', 'Опишіть потребу — її побачать усі волонтери.'],
    assigned: ['Ви нічого не взяли в роботу', 'Відкрийте дошку і оберіть запит.'],
  }[scope];
  return `<div class="empty"><b>${text[0]}</b><p>${text[1]}</p></div>`;
}


/* ---------- екран військового: журнал потреб ---------- */

const LEDGER_ORDER = { pending: 0, in_progress: 1, open: 2, cancelled: 3, completed: 4 };

async function viewLedger() {
  main.innerHTML = `<div class="spinner">завантаження…</div>`;
  const needs = await api('/needs?scope=mine');
  const rows = needs.slice().sort((a, b) => {
    const byStatus = LEDGER_ORDER[a.status] - LEDGER_ORDER[b.status];
    return byStatus !== 0 ? byStatus : new Date(b.updated_at) - new Date(a.updated_at);
  });
  const waiting = rows.filter((n) => n.status === 'pending');

  main.innerHTML = `
    <div class="head">
      <span class="eyebrow">підрозділ · ${esc(nameOf(S.user))}</span>
      <h1>Журнал потреб</h1>
      <p class="lede">Усе, що ви заявили, і на якій воно стадії. Закриття підтверджуєте ви — виконавець лише повідомляє, що готово.</p>
    </div>

    ${waiting.length ? `<section class="attention">
      <h2>Потребує вашого підтвердження — ${waiting.length}</h2>
      ${waiting.map((n) => `<div class="att-row">
        <b>${esc(n.title)}</b>
        <span class="att-who">${esc(nameOf(n.assignee))}</span>
        <button class="btn sm" data-need="${esc(n.id)}">Розглянути</button>
      </div>`).join('')}
    </section>` : ''}

    <div style="margin-bottom:18px"><button class="btn accent" id="new-need">Заявити потребу</button></div>

    ${rows.length ? `<div class="ledger">
      <div class="ledger-head">
        <span>№</span><span>Потреба</span><span>К-сть</span><span>Стан</span><span>Виконавець</span><span>Оновлено</span>
      </div>
      ${rows.map((n, i) => `<button class="ledger-row" data-need="${esc(n.id)}">
        <span class="ledger-idx">${String(i + 1).padStart(2, '0')}</span>
        <span class="ledger-name">
          <b>${esc(n.title)}</b>
          <span>${esc(mark(n.category))} · ${esc(label('urgencies', n.urgency))}</span>
        </span>
        <span class="ledger-qty">${esc(n.quantity)} ${esc(n.unit)}</span>
        <span><span class="stamp ${esc(n.status)}">${esc(label('need_statuses', n.status))}</span></span>
        <span class="ledger-who">${n.assignee ? esc(nameOf(n.assignee)) : '—'}</span>
        <span class="ledger-when">${esc(when(n.updated_at))}</span>
      </button>`).join('')}
    </div>` : `<div class="empty"><b>Журнал порожній</b><p>Заявіть потребу — її одразу побачать усі волонтери на спільній дошці.</p></div>`}
  `;

  bindCards();
  $('new-need').onclick = () => modalCreateNeed(viewLedger);
}

/* ---------- екрани цивільного: підтримка і огляд потреб ---------- */

async function viewSupport() {
  main.innerHTML = `<div class="spinner">завантаження…</div>`;
  const [funds, mine, profile] = await Promise.all([
    api('/funds'),
    api('/my/contributions'),
    api(`/users/${encodeURIComponent(S.user.username)}`),
  ]);
  const active = funds.filter((f) => f.status === 'active');
  const stats = profile.stats;

  main.innerHTML = `
    <div class="head">
      <span class="eyebrow">підтримка</span>
      <h1>Куди йде ваша допомога</h1>
      <p class="lede">Тут не потрібно нічого везти й ні з ким домовлятись. Достатньо закрити частину суми або віддати те, що вже є вдома.</p>
    </div>

    <section class="impact">
      <div class="impact-lead">
        ${money(stats.contributed_total)} грн
        <small>ви внесли за ${stats.contributions_count} ${plural(stats.contributions_count, 'раз', 'рази', 'разів')}</small>
      </div>
      <div class="impact-split">
        <div><span>Донатів речами</span><b>${stats.donations_offered}</b></div>
        <div><span>Зборів триває</span><b>${active.length}</b></div>
        <div><span>Разом зібрано спільнотою</span><b>${money(S.overview ? S.overview.funds_raised : 0)} грн</b></div>
      </div>
    </section>

    <h2>Збори, які ще не закриті</h2>
    ${active.length ? active.map(fundCard).join('')
      : '<div class="empty"><b>Усе закрито</b><p>Наразі відкритих зборів немає — зазирніть згодом.</p></div>'}

    ${mine.length ? `<h2 style="margin-top:34px">Мої внески</h2>
      <div class="mine-list">${mine.map((entry) => `
        <div class="mine-row">
          <b>${esc(entry.fund.title)}</b>
          <span class="amt">${money(entry.contribution.amount)} грн</span>
          <span class="ago">${esc(when(entry.contribution.created_at))}</span>
        </div>`).join('')}</div>` : ''}
  `;

  main.querySelectorAll('[data-give]').forEach((n) => { n.onclick = () => modalContribute(n.dataset.give, viewSupport); });
  main.querySelectorAll('[data-fund]').forEach((n) => { n.onclick = () => openFund(n.dataset.fund); });
}

async function viewGlance() {
  main.innerHTML = `<div class="spinner">завантаження…</div>`;
  const needs = await api('/needs?scope=all');
  const groups = {};
  needs.forEach((n) => { (groups[n.category] = groups[n.category] || []).push(n); });

  main.innerHTML = `
    <div class="head">
      <span class="eyebrow">огляд</span>
      <h1>Що зараз потрібно</h1>
      <p class="lede">Ці позиції закривають волонтери. Ви можете допомогти інакше — грошима до відповідного збору або річчю зі свого дому.</p>
    </div>
    ${Object.keys(groups).length ? Object.entries(groups).map(([category, items]) => `
      <h2 style="margin-top:26px">${esc(label('categories', category))}</h2>
      <div class="glance">
        ${items.map((n) => `<div class="glance-row">
          <span class="g-name">${esc(n.title)}</span>
          <span class="g-qty">${esc(n.quantity)} ${esc(n.unit)}</span>
          <span class="stamp ${esc(n.status)}">${esc(label('need_statuses', n.status))}</span>
        </div>`).join('')}
      </div>
    `).join('') : '<div class="empty"><b>Зараз усе розібрано</b><p>Відкритих потреб немає.</p></div>'}
    <div style="margin-top:30px"><button class="btn accent" id="offer">Віддати щось зі свого</button></div>
  `;

  $('offer').onclick = () => modalCreateDonation(viewGlance);
}

function plural(n, one, few, many) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}

/* ---------- екран: збори ---------- */

const SEGMENTS = 28;

function tally(current, target) {
  const ratio = Math.min(1, current / target);
  const filled = Math.round(ratio * SEGMENTS);
  const done = current >= target;
  let bars = '';
  for (let i = 0; i < SEGMENTS; i += 1) {
    bars += `<i class="${i < filled ? 'f' : ''}"></i>`;
  }
  return `<div class="tally ${done ? 'done' : ''}" role="img"
    aria-label="Зібрано ${Math.round(ratio * 100)} відсотків">${bars}</div>`;
}

function fundCard(fund) {
  const pct = Math.round(Math.min(1, fund.current_amount / fund.target_amount) * 100);
  return `<article class="fund">
    <div class="fund-top">
      <span class="fund-title">${esc(fund.title)}</span>
      <span class="stamp ${esc(fund.status)}">${esc(label('fund_statuses', fund.status))}</span>
    </div>
    <div class="fund-desc">${esc(fund.description)}</div>
    ${tally(fund.current_amount, fund.target_amount)}
    <div class="fund-figures">
      <span class="now">${money(fund.current_amount)}</span>
      <span>із ${money(fund.target_amount)} грн</span>
      <span class="pct">${pct}%</span>
    </div>
    <div class="fund-figures" style="margin-top:6px">
      <span>відкрив ${esc(nameOf(fund.author))}</span>
      <span>${esc(when(fund.created_at))}</span>
      ${fund.requisites ? `<span>${esc(fund.requisites)}</span>` : ''}
    </div>
    <div class="fund-actions">
      ${fund.status === 'active'
        ? `<button class="btn accent sm" data-give="${esc(fund.id)}">Підтримати</button>`
        : ''}
      <button class="btn ghost sm" data-fund="${esc(fund.id)}">Хто підтримав</button>
      ${fund.status === 'active' && fund.author.id === S.user.id
        ? `<button class="btn ghost sm" data-close="${esc(fund.id)}">Завершити збір</button>` : ''}
    </div>
  </article>`;
}

async function viewFunds() {
  main.innerHTML = `<div class="spinner">завантаження…</div>`;
  const funds = await api('/funds');
  const canCreate = S.user.role !== 'civilian';

  main.innerHTML = `
    <div class="head">
      <span class="eyebrow">фінанси</span>
      <h1>Збори</h1>
      <p class="lede">Сума росте з кожного зафіксованого внеску. Коли ціль досягнута, збір закривається сам.</p>
    </div>
    ${canCreate ? `<div style="margin-bottom:18px"><button class="btn accent" id="new-fund">Відкрити збір</button></div>` : ''}
    ${funds.length ? funds.map(fundCard).join('') : '<div class="empty"><b>Зборів поки немає</b><p>Тут зʼявляться відкриті збори на техніку, ремонт і спорядження.</p></div>'}
  `;

  const create = $('new-fund');
  if (create) create.onclick = () => modalCreateFund(viewFunds);
  main.querySelectorAll('[data-give]').forEach((n) => { n.onclick = () => modalContribute(n.dataset.give, viewFunds); });
  main.querySelectorAll('[data-fund]').forEach((n) => { n.onclick = () => openFund(n.dataset.fund); });
  main.querySelectorAll('[data-close]').forEach((n) => {
    n.onclick = async () => {
      await api(`/funds/${n.dataset.close}/close`, { method: 'POST' });
      toast('Збір завершено');
      viewFunds();
    };
  });
}

/* ---------- екран: донати речами ---------- */

function donationCard(donation) {
  const isMine = donation.donor.id === S.user.id;
  return `<article class="fund">
    <div class="fund-top">
      <span class="fund-title">${esc(donation.item)}</span>
      <span class="stamp ${esc(donation.status)}">${esc(label('donation_statuses', donation.status))}</span>
    </div>
    <div class="fund-figures" style="margin-bottom:8px">
      <span><b style="font-family:var(--display);font-size:17px">${esc(donation.quantity)}</b> ${esc(donation.unit)}</span>
      <span>${esc(label('categories', donation.category))}</span>
      <span>${esc(nameOf(donation.donor))}</span>
      <span>${esc(when(donation.created_at))}</span>
    </div>
    ${donation.note ? `<div class="fund-desc">${esc(donation.note)}</div>` : ''}
    ${donation.need ? `<div class="fund-desc">Закріплено за запитом «${esc(donation.need.title)}»</div>` : ''}
    <div class="fund-figures"><span>Звʼязок: <b style="color:var(--ink)">${esc(donation.contact)}</b></span></div>
    ${isMine && donation.status !== 'delivered' ? `<div class="fund-actions">
      ${donation.need
        ? `<button class="btn ghost sm" data-unlink="${esc(donation.id)}">Відкріпити</button>`
        : `<button class="btn ghost sm" data-link="${esc(donation.id)}">Закріпити за запитом</button>`}
      <button class="btn sm" data-delivered="${esc(donation.id)}">Позначити переданим</button>
    </div>` : ''}
  </article>`;
}

async function viewDonations() {
  main.innerHTML = `<div class="spinner">завантаження…</div>`;
  const donations = await api('/donations');

  main.innerHTML = `
    <div class="head">
      <span class="eyebrow">склад</span>
      <h1>Донати речами</h1>
      <p class="lede">Те, що вже є на руках. Позицію можна закріпити за конкретним запитом, щоб двоє людей не везли одне й те саме.</p>
    </div>
    <div style="margin-bottom:18px"><button class="btn accent" id="new-donation">Розмістити донат</button></div>
    ${donations.length ? donations.map(donationCard).join('') : '<div class="empty"><b>Порожньо</b><p>Розмістіть перший донат — його побачать військові й волонтери.</p></div>'}
  `;

  $('new-donation').onclick = () => modalCreateDonation(viewDonations);
  main.querySelectorAll('[data-link]').forEach((n) => { n.onclick = () => modalLinkDonation(n.dataset.link); });
  main.querySelectorAll('[data-unlink]').forEach((n) => {
    n.onclick = async () => {
      await api(`/donations/${n.dataset.unlink}/unlink`, { method: 'POST' });
      toast('Донат повернено у вільні');
      viewDonations();
    };
  });
  main.querySelectorAll('[data-delivered]').forEach((n) => {
    n.onclick = async () => {
      await api(`/donations/${n.dataset.delivered}/status`, { method: 'POST', body: { status: 'delivered' } });
      toast('Позначено переданим');
      viewDonations();
    };
  });
}

/* ---------- екран: стрічка ---------- */

const FEED_TEXT = {
  user_joined: (a, p) => [`<b>${a}</b> приєднався як ${esc(label('roles', p.role))}`, ''],
  need_created: (a, p) => [`<b>${a}</b> опублікував запит «${esc(p.title)}»`, p.urgency === 'critical' ? 'hot' : ''],
  need_taken: (a, p) => [`<b>${a}</b> узяв у роботу «${esc(p.title)}»`, ''],
  need_released: (a, p) => [`<b>${a}</b> повернув на дошку «${esc(p.title)}»`, ''],
  need_submitted: (a, p) => [`<b>${a}</b> позначив виконаним «${esc(p.title)}» — чекає підтвердження`, ''],
  need_confirmed: (a, p) => [`<b>${a}</b> підтвердив виконання «${esc(p.title)}»`, 'good'],
  need_rejected: (a, p) => [`<b>${a}</b> відхилив виконання «${esc(p.title)}»`, 'hot'],
  need_cancelled: (a, p) => [`<b>${a}</b> скасував запит «${esc(p.title)}»`, ''],
  fund_created: (a, p) => [`<b>${a}</b> відкрив збір «${esc(p.title)}» на ${money(p.target)} грн`, ''],
  fund_contributed: (a, p) => [`<b>${a}</b> вніс ${money(p.amount)} грн до «${esc(p.title)}»`, ''],
  fund_closed: (a, p) => [`Збір «${esc(p.title)}» завершено — ${money(p.total)} грн`, 'good'],
  donation_offered: (a, p) => [`<b>${a}</b> віддає ${esc(p.item)} — ${esc(p.quantity)} ${esc(p.unit)}`, ''],
  donation_reserved: (a, p) => [`<b>${a}</b> закріпив ${esc(p.item)} за «${esc(p.title)}»`, ''],
  donation_delivered: (a, p) => [`<b>${a}</b> передав ${esc(p.item)}`, 'good'],
};

function feedItem(activity) {
  const build = FEED_TEXT[activity.kind];
  const actor = esc(nameOf(activity.actor));
  const [text, tone] = build ? build(actor, activity.payload || {}) : [`<b>${actor}</b> ${esc(activity.kind)}`, ''];
  return `<div class="feed-item ${tone}">
    <div class="feed-text">${text}</div>
    <div class="feed-when">${esc(when(activity.created_at))}</div>
  </div>`;
}

async function viewFeed() {
  main.innerHTML = `<div class="spinner">завантаження…</div>`;
  const activities = await api('/feed?limit=80');
  main.innerHTML = `
    <div class="head">
      <span class="eyebrow">хроніка</span>
      <h1>Стрічка</h1>
      <p class="lede">Кожна дія лишає слід: хто взяв запит, хто підтвердив, хто вніс і скільки.</p>
    </div>
    <div class="feed">${activities.map(feedItem).join('')}</div>
  `;
}

/* ---------- екран: дошка пошани ---------- */

async function viewLeaders() {
  main.innerHTML = `<div class="spinner">завантаження…</div>`;
  const rows = await api('/stats/leaderboard');
  main.innerHTML = `
    <div class="head">
      <span class="eyebrow">підсумки</span>
      <h1>Дошка пошани</h1>
      <p class="lede">Рахуються тільки підтверджені запити — ті, що автор прийняв.</p>
    </div>
    ${rows.length ? `<div class="rows">${rows.map((row, index) => `
      <div class="row">
        <span class="rank ${index < 3 ? 'top' : ''}">${index + 1}</span>
        <div class="avatar">${esc(initials(row.user))}</div>
        <div class="who">
          <b>${esc(nameOf(row.user))}</b>
          <span>${esc(label('roles', row.user.role))}</span>
        </div>
        <div class="fig">${row.completed}<small>закрито</small></div>
        <div class="fig">${money(row.contributed)}<small>внесено, грн</small></div>
      </div>
    `).join('')}</div>` : '<div class="empty"><b>Поки порожньо</b><p>Тут зʼявляться ті, хто закриває запити й підтримує збори.</p></div>'}
  `;
}

/* ---------- екран: профіль ---------- */

async function viewProfile(username) {
  const target = username || S.user.username;
  main.innerHTML = `<div class="spinner">завантаження…</div>`;
  const { user, stats } = await api(`/users/${encodeURIComponent(target)}`);
  const isMe = user.id === S.user.id;

  const figures = [
    ['Створено запитів', stats.needs_created],
    ['Закрито запитів', stats.needs_completed],
    ['Зараз у роботі', stats.needs_in_progress],
    ['Внесено, грн', money(stats.contributed_total)],
    ['Донатів речами', stats.donations_offered],
    ['Відкрито зборів', stats.funds_created],
  ];

  main.innerHTML = `
    <div class="head">
      <span class="eyebrow">${isMe ? 'мій профіль' : 'профіль'}</span>
      <div style="display:flex;align-items:center;gap:14px">
        <div class="avatar lg">${esc(initials(user))}</div>
        <div>
          <h1 style="margin-bottom:2px">${esc(nameOf(user))}</h1>
          <p class="lede" style="font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)">
            ${esc(label('roles', user.role))} · @${esc(user.username)} · з ${new Date(user.created_at).toLocaleDateString('uk-UA')}
          </p>
        </div>
      </div>
    </div>
    ${user.about ? `<p class="lede" style="margin-bottom:18px">${esc(user.about)}</p>` : ''}
    <div class="strip">${figures.map(([lbl, num]) => `
      <div class="cell"><span class="num">${esc(num)}</span><span class="lbl">${esc(lbl)}</span></div>
    `).join('')}</div>
    ${user.contact ? `<div class="detail-block"><h3>Звʼязок</h3><div>${esc(user.contact)}</div></div>` : ''}
    ${isMe ? `<button class="btn ghost" id="edit-profile">Редагувати профіль</button>` : ''}
  `;

  const edit = $('edit-profile');
  if (edit) edit.onclick = () => modalEditProfile(() => viewProfile());
}

/* ---------- модальні вікна ---------- */

function closeModal() {
  modalRoot.hidden = true;
  modalRoot.innerHTML = '';
}

function showModal(title, bodyHtml, footHtml = '') {
  modalRoot.hidden = false;
  modalRoot.innerHTML = `<div class="modal" role="dialog" aria-modal="true">
    <div class="modal-head"><h2>${title}</h2><button class="x" id="modal-x" aria-label="Закрити">×</button></div>
    <div class="modal-body">${bodyHtml}</div>
    ${footHtml ? `<div class="modal-foot">${footHtml}</div>` : ''}
  </div>`;
  $('modal-x').onclick = closeModal;
  modalRoot.onclick = (event) => { if (event.target === modalRoot) closeModal(); };
}

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !modalRoot.hidden) closeModal();
});

function options(group) {
  return (S.meta[group] || []).map((o) => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('');
}

function modalCreateNeed(after) {
  showModal('Новий запит', `
    <div class="field"><label for="n-title">Що потрібно</label><input id="n-title" maxlength="160" placeholder="Наприклад: турнікети CAT Gen7"></div>
    <div class="field"><label for="n-desc">Подробиці</label><textarea id="n-desc" maxlength="4000" placeholder="Що саме підходить, а що ні. Чим конкретніше — тим менше зайвих поїздок."></textarea></div>
    <div class="field-row">
      <div class="field"><label for="n-cat">Категорія</label><select id="n-cat">${options('categories')}</select></div>
      <div class="field"><label for="n-urg">Пріоритет</label><select id="n-urg">${options('urgencies')}</select></div>
    </div>
    <div class="field-row">
      <div class="field"><label for="n-qty">Кількість</label><input id="n-qty" type="number" min="1" value="1"></div>
      <div class="field"><label for="n-unit">Одиниця</label><input id="n-unit" value="шт" maxlength="24"></div>
    </div>
    <div class="field"><label for="n-loc">Місце передачі</label><input id="n-loc" maxlength="120" placeholder="не обовʼязково"></div>
  `, `<button class="btn accent" id="n-save">Опублікувати</button><button class="btn ghost" id="n-cancel">Скасувати</button>`);

  $('n-urg').value = 'normal';
  $('n-cancel').onclick = closeModal;
  $('n-save').onclick = async (event) => {
    event.target.disabled = true;
    try {
      await api('/needs', { method: 'POST', body: {
        title: $('n-title').value.trim(),
        description: $('n-desc').value.trim(),
        category: $('n-cat').value,
        urgency: $('n-urg').value,
        quantity: Number($('n-qty').value) || 1,
        unit: $('n-unit').value.trim() || 'шт',
        location: $('n-loc').value.trim() || null,
      }});
      closeModal();
      toast('Запит опубліковано');
      await refreshOverview();
      after();
    } catch { event.target.disabled = false; }
  };
}

function modalCreateFund(after) {
  showModal('Новий збір', `
    <div class="field"><label for="f-title">Назва збору</label><input id="f-title" maxlength="160"></div>
    <div class="field"><label for="f-desc">На що збираємо</label><textarea id="f-desc" maxlength="4000"></textarea></div>
    <div class="field-row">
      <div class="field"><label for="f-target">Ціль, грн</label><input id="f-target" type="number" min="1" value="10000"></div>
      <div class="field"><label for="f-req">Реквізити</label><input id="f-req" maxlength="200" placeholder="посилання на банку"></div>
    </div>
  `, `<button class="btn accent" id="f-save">Відкрити збір</button><button class="btn ghost" id="f-cancel">Скасувати</button>`);

  $('f-cancel').onclick = closeModal;
  $('f-save').onclick = async (event) => {
    event.target.disabled = true;
    try {
      await api('/funds', { method: 'POST', body: {
        title: $('f-title').value.trim(),
        description: $('f-desc').value.trim(),
        target_amount: Number($('f-target').value) || 1,
        requisites: $('f-req').value.trim() || null,
      }});
      closeModal();
      toast('Збір відкрито');
      await refreshOverview();
      after();
    } catch { event.target.disabled = false; }
  };
}

function modalContribute(fundId, after = viewFunds) {
  showModal('Підтримати збір', `
    <p class="lede" style="margin-bottom:16px">Спершу перекажіть кошти за реквізитами збору, потім зафіксуйте суму тут — вона одразу відобразиться на шкалі.</p>
    <div class="field"><label for="c-amount">Сума, грн</label><input id="c-amount" type="number" min="1" value="500"></div>
    <div class="field"><label for="c-comment">Коментар</label><input id="c-comment" maxlength="200" placeholder="не обовʼязково"></div>
  `, `<button class="btn accent" id="c-save">Зафіксувати внесок</button><button class="btn ghost" id="c-cancel">Скасувати</button>`);

  $('c-cancel').onclick = closeModal;
  $('c-save').onclick = async (event) => {
    event.target.disabled = true;
    try {
      await api(`/funds/${fundId}/contribute`, { method: 'POST', body: {
        amount: Number($('c-amount').value) || 0,
        comment: $('c-comment').value.trim() || null,
      }});
      closeModal();
      toast('Дякуємо, внесок зафіксовано');
      await refreshOverview();
      after();
    } catch { event.target.disabled = false; }
  };
}

function modalCreateDonation(after) {
  showModal('Розмістити донат', `
    <div class="field"><label for="d-item">Що віддаєте</label><input id="d-item" maxlength="160" placeholder="Наприклад: павербанки 20000 mAh"></div>
    <div class="field-row">
      <div class="field"><label for="d-qty">Кількість</label><input id="d-qty" type="number" min="1" value="1"></div>
      <div class="field"><label for="d-unit">Одиниця</label><input id="d-unit" value="шт" maxlength="24"></div>
    </div>
    <div class="field"><label for="d-cat">Категорія</label><select id="d-cat">${options('categories')}</select></div>
    <div class="field"><label for="d-contact">Контакт</label><input id="d-contact" maxlength="120" placeholder="@нік або телефон"></div>
    <div class="field"><label for="d-note">Примітка</label><textarea id="d-note" maxlength="1000" placeholder="Стан, чи можете привезти самі, коли зручно забрати"></textarea></div>
  `, `<button class="btn accent" id="d-save">Розмістити</button><button class="btn ghost" id="d-cancel">Скасувати</button>`);

  $('d-contact').value = S.user.contact || '';
  $('d-cancel').onclick = closeModal;
  $('d-save').onclick = async (event) => {
    event.target.disabled = true;
    try {
      await api('/donations', { method: 'POST', body: {
        item: $('d-item').value.trim(),
        quantity: Number($('d-qty').value) || 1,
        unit: $('d-unit').value.trim() || 'шт',
        category: $('d-cat').value,
        contact: $('d-contact').value.trim(),
        note: $('d-note').value.trim() || null,
      }});
      closeModal();
      toast('Донат розміщено');
      await refreshOverview();
      after();
    } catch { event.target.disabled = false; }
  };
}

async function modalLinkDonation(donationId) {
  const needs = await api('/needs?scope=all');
  showModal('Закріпити за запитом', `
    <p class="lede" style="margin-bottom:16px">Оберіть запит, який закриває ця позиція. Донат перейде у стан «Закріплено».</p>
    <div class="field"><label for="l-need">Запит</label><select id="l-need">
      ${needs.map((n) => `<option value="${esc(n.id)}">${esc(n.title)} — ${esc(n.quantity)} ${esc(n.unit)}</option>`).join('')}
    </select></div>
  `, `<button class="btn accent" id="l-save">Закріпити</button><button class="btn ghost" id="l-cancel">Скасувати</button>`);

  $('l-cancel').onclick = closeModal;
  $('l-save').onclick = async (event) => {
    event.target.disabled = true;
    try {
      await api(`/donations/${donationId}/link/${$('l-need').value}`, { method: 'POST' });
      closeModal();
      toast('Закріплено за запитом');
      viewDonations();
    } catch { event.target.disabled = false; }
  };
}

function modalEditProfile(after) {
  showModal('Профіль', `
    <div class="field-row">
      <div class="field"><label for="p-first">Імʼя</label><input id="p-first" maxlength="64" value="${esc(S.user.first_name)}"></div>
      <div class="field"><label for="p-last">Прізвище</label><input id="p-last" maxlength="64" value="${esc(S.user.last_name)}"></div>
    </div>
    <div class="field-row">
      <div class="field"><label for="p-callsign">Позивний</label><input id="p-callsign" maxlength="48" value="${esc(S.user.callsign || '')}"></div>
      <div class="field"><label for="p-contact">Контакт</label><input id="p-contact" maxlength="120" value="${esc(S.user.contact || '')}"></div>
    </div>
    <div class="field"><label for="p-about">Про себе</label><textarea id="p-about" maxlength="600">${esc(S.user.about || '')}</textarea></div>
  `, `<button class="btn accent" id="p-save">Зберегти</button><button class="btn ghost" id="p-cancel">Скасувати</button>`);

  $('p-cancel').onclick = closeModal;
  $('p-save').onclick = async (event) => {
    event.target.disabled = true;
    try {
      S.user = await api('/auth/me', { method: 'PATCH', body: {
        first_name: $('p-first').value.trim(),
        last_name: $('p-last').value.trim(),
        callsign: $('p-callsign').value.trim() || null,
        contact: $('p-contact').value.trim() || null,
        about: $('p-about').value.trim() || null,
      }});
      closeModal();
      toast('Збережено');
      renderRail();
      after();
    } catch { event.target.disabled = false; }
  };
}

/* ---------- деталі запиту ---------- */

async function openNeed(needId) {
  const { need, history, donations, funds } = await api(`/needs/${needId}`);
  const isAuthor = need.author.id === S.user.id;
  const isAssignee = need.assignee && need.assignee.id === S.user.id;
  const canTake = S.user.role === 'volunteer' && need.status === 'open';

  const actions = [];
  if (canTake) actions.push(`<button class="btn accent" data-act="take">Взяти в роботу</button>`);
  if (isAssignee && need.status === 'in_progress') {
    actions.push(`<button class="btn accent" data-act="submit">Надіслати на підтвердження</button>`);
    actions.push(`<button class="btn ghost" data-act="release">Відмовитись</button>`);
  }
  if (isAuthor && need.status === 'pending') {
    actions.push(`<button class="btn accent" data-act="confirm">Підтвердити виконання</button>`);
    actions.push(`<button class="btn danger" data-act="reject">Відхилити</button>`);
  }
  if (isAuthor && !['completed', 'cancelled'].includes(need.status)) {
    actions.push(`<button class="btn ghost" data-act="cancel">Скасувати запит</button>`);
  }

  showModal(
    `${esc(need.title)} <span class="stamp ${esc(need.status)}" style="margin-left:8px">${esc(label('need_statuses', need.status))}</span>`,
    `
    <div class="detail-block">
      <h3>Опис</h3>
      <div>${esc(need.description)}</div>
    </div>
    <div class="detail-block">
      <h3>Картка</h3>
      <dl class="kv">
        <dt>Потрібно</dt><dd>${esc(need.quantity)} ${esc(need.unit)}</dd>
        <dt>Категорія</dt><dd>${esc(label('categories', need.category))} · ${esc(mark(need.category))}</dd>
        <dt>Пріоритет</dt><dd>${esc(label('urgencies', need.urgency))}</dd>
        <dt>Автор</dt><dd>${esc(nameOf(need.author))}${need.author.contact ? ` · ${esc(need.author.contact)}` : ''}</dd>
        ${need.assignee ? `<dt>Виконує</dt><dd>${esc(nameOf(need.assignee))}</dd>` : ''}
        ${need.location ? `<dt>Місце</dt><dd>${esc(need.location)}</dd>` : ''}
        <dt>Створено</dt><dd>${new Date(need.created_at).toLocaleString('uk-UA')}</dd>
      </dl>
    </div>
    ${donations.length ? `<div class="detail-block"><h3>Закріплені донати</h3>
      ${donations.map((d) => `<div>${esc(d.item)} — ${esc(d.quantity)} ${esc(d.unit)} · ${esc(nameOf(d.donor))}</div>`).join('')}
    </div>` : ''}
    ${funds.length ? `<div class="detail-block"><h3>Повʼязані збори</h3>
      ${funds.map((f) => `<div>${esc(f.title)} — ${money(f.current_amount)} / ${money(f.target_amount)} грн</div>`).join('')}
    </div>` : ''}
    <div class="detail-block">
      <h3>Історія</h3>
      <div class="feed">${history.slice().reverse().map(feedItem).join('')}</div>
    </div>
  `, actions.join(''));

  modalRoot.querySelectorAll('[data-act]').forEach((node) => {
    node.onclick = async () => {
      const act = node.dataset.act;
      const needsComment = ['submit', 'confirm', 'reject', 'cancel'].includes(act);
      let comment = null;
      if (act === 'reject' || act === 'cancel') {
        comment = prompt(act === 'reject' ? 'Чому відхиляєте?' : 'Причина скасування:') || null;
      }
      modalRoot.querySelectorAll('[data-act]').forEach((b) => { b.disabled = true; });
      try {
        await api(`/needs/${needId}/${act}`, {
          method: 'POST',
          body: needsComment ? { comment } : undefined,
        });
        closeModal();
        toast('Готово');
        await refreshOverview();
        route();
      } catch {
        modalRoot.querySelectorAll('[data-act]').forEach((b) => { b.disabled = false; });
      }
    };
  });
}

async function openFund(fundId) {
  const { fund, contributions } = await api(`/funds/${fundId}`);
  showModal(esc(fund.title), `
    ${tally(fund.current_amount, fund.target_amount)}
    <div class="fund-figures" style="margin-bottom:18px">
      <span class="now">${money(fund.current_amount)}</span>
      <span>із ${money(fund.target_amount)} грн</span>
    </div>
    <div class="detail-block">
      <h3>Внески (${contributions.length})</h3>
      ${contributions.length ? `<div class="rows">${contributions.map((c) => `
        <div class="row">
          <div class="avatar">${esc(initials(c.user))}</div>
          <div class="who"><b>${esc(nameOf(c.user))}</b><span>${esc(when(c.created_at))}</span></div>
          <div class="fig">${money(c.amount)}<small>грн</small></div>
        </div>
      `).join('')}</div>` : '<div class="empty"><b>Ще ніхто не підтримав</b><p>Будьте першим.</p></div>'}
      ${contributions.some((c) => c.comment) ? `<div style="margin-top:12px">${contributions.filter((c) => c.comment).map((c) => `<div class="fund-desc">«${esc(c.comment)}» — ${esc(nameOf(c.user))}</div>`).join('')}</div>` : ''}
    </div>
  `);
}

/* ---------- маршрутизація ---------- */

const ROUTES = {
  ledger: viewLedger,
  support: viewSupport,
  glance: viewGlance,
  board: () => viewBoard('all'),
  mine: () => viewBoard('mine'),
  assigned: () => viewBoard('assigned'),
  funds: viewFunds,
  donations: viewDonations,
  feed: viewFeed,
  leaders: viewLeaders,
  profile: () => viewProfile(),
};

async function route() {
  const home = HOME[S.user.role] || 'board';
  const [name, arg] = (location.hash.replace('#/', '') || home).split('/');
  const allowed = (NAV[S.user.role] || []).some((item) => item.id === name);
  const handler = allowed || name === 'user' ? ROUTES[name] : null;
  S.view = allowed ? name : home;
  renderRail();
  try {
    if (name === 'user' && arg) await viewProfile(arg);
    else await (handler || ROUTES[home])();
  } catch (error) {
    main.innerHTML = `<div class="empty"><b>Не вдалося завантажити</b><p>${esc(error.message)}</p></div>`;
  }
}

async function refreshOverview() {
  try { S.overview = await api('/stats/overview', { quiet: true }); } catch { /* не критично */ }
  renderRail();
}

/* ---------- старт ---------- */

async function boot() {
  if (!S.token) { viewGate('login'); return; }
  try {
    if (!S.user) S.user = await api('/auth/me', { quiet: true });
    S.meta = await api('/meta', { quiet: true });
  } catch {
    signOut();
    return;
  }
  document.documentElement.dataset.role = S.user.role;
  gate.hidden = true;
  app.hidden = false;
  await refreshOverview();
  await route();
}

window.addEventListener('hashchange', () => { if (S.user) route(); });
boot();
