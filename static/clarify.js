const $ = (id) => document.getElementById(id);

let state = null;
let sessionId = null;
let lastGroup = null;
let shownIntro = false;
let shownReady = false;
let expanded = new Set();

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function showErr(text) {
  const box = $('err');
  box.textContent = text;
  box.hidden = false;
}

function clearErr() {
  $('err').hidden = true;
}

async function api(path, body) {
  const options = body === undefined
    ? {}
    : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok || (payload.code && payload.code !== 0)) {
    throw new Error(payload.msg || '请求失败');
  }
  return payload.data;
}

function bubble(who, html, cls) {
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  el.innerHTML = '<div class="who">' + who + '</div>' + html;
  $('chat').appendChild(el);
  $('chat').scrollTop = $('chat').scrollHeight;
  return el;
}

function renderSide(data) {
  const groups = [...new Set(data.items.map((i) => i.group))];
  $('items').innerHTML = groups.map((g) => '<div class="group"><h4>' + g + '</h4>' +
    data.items.map((item, idx) => {
      if (item.group !== g) return '';
      const ok = item.status === 'confirmed';
      const tag = ok ? '已定' : item.tag;
      const cls = ok ? 'said' : (item.tag === '歧义' ? 'amb' : '');
      const row = '<div class="row ' + (ok ? 'ok' : '') + '" data-idx="' + idx + '">' +
        '<span class="dot"></span><span class="k">' + esc(item.key) + '</span>' +
        '<span class="v">' + esc(item.value || '待你拍板') + '</span>' +
        '<span class="tag ' + cls + '">' + tag + '</span></div>';
      const detail = expanded.has(idx)
        ? '<div class="detail"><b>为什么必须问：</b>' + esc(item.why) +
          '<br><b>真实例子：</b>' + esc(item.example) +
          '<br><b>当前规则：</b>' + esc(item.value || '尚未定死') + '</div>'
        : '';
      return row + detail;
    }).join('') + '</div>').join('');

  $('bar').style.width = Math.round(data.confirmed / data.total * 100) + '%';
  $('badge').textContent = data.status === 'ready' ? '全部钉死' : '已定 ' + data.confirmed + ' / ' + data.total;
  $('badge').className = 'badge' + (data.status === 'ready' ? ' ready' : '');
  $('phase').textContent = data.status === 'ready'
    ? '理解完成'
    : (data.current_group || '待开始') + ' · 待定 ' + data.pending + ' 项';
  $('rules-head').textContent = '拍板后的可执行判定规则（' + data.rules.length + ' / ' + data.total + '）';
  $('rules').innerHTML = data.rules.map((r, i) =>
    '<div>' + (i + 1) + '. <b>' + esc(r.key) + '</b>：' + esc(r.rule) + '</div>').join('');
  $('confirm').disabled = data.status !== 'ready';
  $('tip').textContent = data.status === 'ready'
    ? '标准已全部锁定，确认后只产出规格，本阶段不抓取'
    : '还有 ' + data.pending + ' 个模糊项，一个都不会替你猜';
}

function questionCard(questions, group) {
  const el = document.createElement('div');
  el.className = 'msg ai';
  let html = '<div class="who">Lioran</div><div><b>' + esc(group) + '</b>：这一组 ' +
    questions.length + ' 项，逐项定死。每项都写了为什么问。</div>';
  questions.forEach((q) => {
    html += '<div class="q"><p><span class="label">' + q.tag + '</span>' + esc(q.question) +
      '<br><span style="font-size:11px;color:#6b7280">→ 定的是「' + esc(q.key) + '」这一项</span></p>' +
      '<div class="qwhy"><b>为什么必须问：</b>' + esc(q.why) +
      '<br><b>真实例子：</b>' + esc(q.example) + '</div>' +
      '<div class="opts">' + q.options.map((o) =>
        '<button class="opt" data-id="' + q.id + '" data-val="' + esc(o) + '">' + esc(o) + '</button>'
      ).join('') + '</div></div>';
  });
  html += '<button class="submit" disabled>提交这一组</button>';
  el.innerHTML = html;

  const picked = {};
  const submit = el.querySelector('.submit');
  el.querySelectorAll('.opt').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      el.querySelectorAll('.opt[data-id="' + id + '"]').forEach((x) => x.classList.remove('on'));
      btn.classList.add('on');
      picked[id] = btn.dataset.val;
      submit.disabled = Object.keys(picked).length < questions.length;
    });
  });
  submit.addEventListener('click', async () => {
    submit.disabled = true;
    try {
      clearErr();
      const data = await api('/api/clarify/' + sessionId + '/answer', { answers: picked });
      el.querySelectorAll('.opt').forEach((b) => { b.disabled = true; });
      bubble('你', esc(questions.map((q) => '· ' + q.key + '：' + picked[q.id]).join('\n')), 'user');
      render(data);
    } catch (error) {
      showErr(error.message);
      submit.disabled = false;
    }
  });
  $('chat').appendChild(el);
  $('chat').scrollTop = $('chat').scrollHeight;
}

function render(data) {
  const first = !state;
  state = data;
  sessionId = data.session_id;
  renderSide(data);

  if (first && !shownIntro) {
    bubble('Lioran', esc(data.understanding), 'ai');
    shownIntro = true;
  }
  if (data.questions.length && (!lastGroup || lastGroup !== data.current_group)) {
    questionCard(data.questions, data.current_group);
  }
  if (data.status === 'ready' && !shownReady) {
    bubble('Lioran', '<b>' + data.total + ' 项标准全部钉死了</b>，右侧是整套可执行判定规则，' +
      '没有一处是系统替你猜的。点「确认并锁定规格」后本阶段结束；<b>抓取不在这一步执行</b>。', 'ai');
    shownReady = true;
  }
  lastGroup = data.current_group;
}

$('items').addEventListener('click', (event) => {
  const row = event.target.closest('.row');
  if (!row || !state) return;
  const idx = Number(row.dataset.idx);
  if (expanded.has(idx)) expanded.delete(idx);
  else expanded.add(idx);
  renderSide(state);
});

$('start').addEventListener('click', async () => {
  clearErr();
  $('start').disabled = true;
  try {
    const data = await api('/api/clarify', {
      url: $('url').value.trim(),
      requirement: $('requirement').value.trim(),
      review: $('review').value.trim()
    });
    sessionStorage.removeItem('lioran-clarify-spec');
    $('chat').innerHTML = '';
    state = null;
    lastGroup = null;
    shownIntro = false;
    shownReady = false;
    expanded = new Set();
    render(data);
  } catch (error) {
    showErr(error.message);
  } finally {
    $('start').disabled = false;
  }
});

$('confirm').addEventListener('click', async () => {
  clearErr();
  try {
    const spec = await api('/api/clarify/' + sessionId + '/confirm', {});
    sessionStorage.setItem('lioran-clarify-spec', JSON.stringify({
      url: spec.url,
      requirement: spec.requirement,
      review: spec.review,
      session_id: spec.session_id,
      confirmed_at: spec.confirmed_at,
      pending: 0,
      spec: spec.spec
    }));
    bubble('Lioran', '<b>规格已锁定</b>：共 ' + spec.spec.length +
      ' 条可执行判定规则。本阶段只做「理解 + 提问」这一层，抓取与筛选代码未改动、也未触发。', 'ai');
    $('confirm').disabled = true;
    $('tip').textContent = '规格已锁定。返回提取页后，再点一次才会走现有抓取；这一步没有开始抓取。';
  } catch (error) {
    showErr(error.message);
  }
});

$('send-note').addEventListener('click', async () => {
  const text = $('note').value.trim();
  if (!text || !sessionId) return;
  $('note').value = '';
  clearErr();
  bubble('你', esc(text), 'user');
  try {
    const data = await api('/api/clarify/' + sessionId + '/note', { text });
    render(data.state);
    const el = bubble('Lioran', '<div>' + esc(data.question) + '</div>', 'ai');
    if (!data.affected_ids.length) return;
    const box = document.createElement('div');
    box.className = 'recheck';
    box.innerHTML = data.affected_ids.map((id) => {
      const item = state.items.find((i) => i.id === id);
      return '<label><input type="checkbox" value="' + id + '" checked> ' +
        esc(item ? item.key : id) + '</label>';
    }).join('') + '<button class="submit" style="margin-top:8px">重新确认选中项</button>';
    el.appendChild(box);
    box.querySelector('.submit').addEventListener('click', async () => {
      const ids = [...box.querySelectorAll('input:checked')].map((i) => i.value);
      try {
        const next = await api('/api/clarify/' + sessionId + '/recheck', { item_ids: ids });
        if (next.pending > 0) sessionStorage.removeItem('lioran-clarify-spec');
        lastGroup = null;
        shownReady = false;
        render(next);
      } catch (error) {
        showErr(error.message);
      }
    });
  } catch (error) {
    showErr(error.message);
  }
});

$('note').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') $('send-note').click();
});

const incoming = new URLSearchParams(location.search);
if (incoming.get('url')) $('url').value = incoming.get('url');
if (incoming.get('requirement')) $('requirement').value = incoming.get('requirement');
if (incoming.has('review')) $('review').value = incoming.get('review');

function syncBackHome() {
  const params = new URLSearchParams();
  const url = $('url').value.trim();
  const requirement = $('requirement').value.trim();
  if (url) params.set('url', url);
  if (requirement) params.set('requirement', requirement);
  const maxPages = incoming.get('max_pages');
  if (maxPages) params.set('max_pages', maxPages);
  const query = params.toString();
  $('back-home').href = query ? '/?' + query : '/';
}

syncBackHome();
['url', 'requirement'].forEach((id) => $(id).addEventListener('input', syncBackHome));
if (incoming.get('url') && incoming.get('requirement')) $('start').click();
