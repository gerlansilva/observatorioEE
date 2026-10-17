const $ = (selector, root = document) => root.querySelector(selector);
const TOKEN_KEY = 'observatorioEE.adminToken';

const state = {
  token: sessionStorage.getItem(TOKEN_KEY) || '',
  items: [],
  current: null,
  isNew: false,
};

const fields = {
  id: '#field-id',
  titulo: '#field-titulo',
  autor: '#field-autor',
  orientador: '#field-orientador',
  ano: '#field-ano',
  tipo: '#field-tipo',
  grau: '#field-grau',
  instituicao: '#field-instituicao',
  programa: '#field-programa',
  cidade: '#field-cidade',
  estado: '#field-estado',
  regiao: '#field-regiao',
  area: '#field-area',
  nivel: '#field-nivel',
  foco: '#field-foco',
  conteudo: '#field-conteudo',
  resumo: '#field-resumo',
  resumo_idioma: '#field-resumo_idioma',
  resumo_fonte: '#field-resumo_fonte',
  tags: '#field-tags',
  problema: '#field-problema',
  link_bdtd: '#field-link_bdtd',
  link_registro: '#field-link_registro',
  link_texto: '#field-link_texto',
  link_scholar: '#field-link_scholar',
};

function setStatus(message, error = false) {
  const status = $('#status');
  status.textContent = message;
  status.classList.toggle('is-error', error);
}

function showApp(show) {
  $('#login').hidden = show;
  $('#app').hidden = !show;
  $('#logout').hidden = !show;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { 'content-type': 'application/json' } : {}),
      authorization: `Bearer ${state.token}`,
      ...options.headers,
    },
  });
  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (response.status === 401) {
    sessionStorage.removeItem(TOKEN_KEY);
    showApp(false);
    $('#login-note').textContent = 'Sessão expirada. Informe o token novamente.';
    throw new Error('Não autorizado.');
  }
  if (!response.ok) throw new Error(data.error || 'Falha na operação.');
  return data;
}

function slug(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function uniqueId(base) {
  let id = base || 'novo-trabalho';
  let suffix = 2;
  const existing = new Set(state.items.map((item) => item.id));
  while (existing.has(id)) {
    id = `${base}-${suffix}`;
    suffix += 1;
  }
  return id;
}

function suggestedId() {
  const author = $('#field-autor')?.value || '';
  const year = $('#field-ano')?.value || '';
  const surname = author.trim().split(/\s+/).pop() || 'trabalho';
  return uniqueId(slug(`${surname}-${year || new Date().getFullYear()}`));
}

function fillForm(item, isNew = false) {
  state.current = item;
  state.isNew = isNew;
  const set = (selector, value) => {
    const input = $(selector);
    if (input) input.value = value ?? '';
  };
  set(fields.id, item.id || '');
  set(fields.titulo, item.titulo);
  set(fields.autor, item.autor);
  set(fields.orientador, item.orientador);
  set(fields.ano, item.ano);
  set(fields.tipo, item.tipo || 'Dissertação');
  set(fields.grau, item.grau || 'Mestrado Acadêmico');
  set(fields.instituicao, item.instituicao);
  set(fields.programa, item.programa);
  set(fields.cidade, item.cidade);
  set(fields.estado, item.estado);
  set(fields.regiao, item.regiao);
  set(fields.area, item.area);
  set(fields.nivel, item.nivel);
  set(fields.foco, item.foco);
  set(fields.conteudo, item.conteudo);
  set(fields.resumo, item.resumo);
  set(fields.resumo_idioma, item.resumo_idioma || 'por');
  set(fields.resumo_fonte, item.resumo_fonte);
  set(fields.tags, Array.isArray(item.tags) ? item.tags.join('; ') : '');
  set(fields.problema, item.problema);
  set(fields.link_bdtd, item.links?.bdtd_registro);
  set(fields.link_registro, item.links?.registro_institucional);
  set(fields.link_texto, item.links?.texto_completo);
  set(fields.link_scholar, item.links?.google_scholar);

  $('#field-id').readOnly = !isNew;
  $('#editor-mode').textContent = isNew ? 'Nova ficha' : 'Editando ficha';
  $('#editor-title').textContent = isNew ? 'Novo trabalho' : item.titulo || item.id;
  $('#item-form').hidden = false;
  $('#empty-editor').hidden = true;
  $('#save-item').disabled = false;
  $('#delete-item').hidden = isNew;
  setStatus('');
  $('#field-titulo').focus();
}

function collect() {
  const value = (selector) => $(selector)?.value.trim() || '';
  const id = value(fields.id);
  const item = state.current && !state.isNew ? { ...state.current } : {};
  item.id = id;
  item.titulo = value(fields.titulo);
  item.autor = value(fields.autor);
  item.orientador = value(fields.orientador);
  item.ano = Number(value(fields.ano)) || '';
  item.tipo = value(fields.tipo);
  item.grau = value(fields.grau);
  item.instituicao = value(fields.instituicao);
  item.programa = value(fields.programa);
  item.cidade = value(fields.cidade);
  item.estado = value(fields.estado);
  item.regiao = value(fields.regiao);
  item.area = value(fields.area);
  item.nivel = value(fields.nivel);
  item.foco = value(fields.foco);
  item.conteudo = value(fields.conteudo);
  item.resumo = value(fields.resumo);
  item.resumo_idioma = value(fields.resumo_idioma) || 'por';
  item.resumo_fonte = value(fields.resumo_fonte);
  item.problema = value(fields.problema);
  item.tags = value(fields.tags)
    .split(/[;,]/)
    .map((tag) => tag.trim())
    .filter(Boolean);

  const links = { ...(state.current?.links || {}) };
  const linkValues = {
    bdtd_registro: value(fields.link_bdtd),
    registro_institucional: value(fields.link_registro),
    texto_completo: value(fields.link_texto),
    google_scholar: value(fields.link_scholar),
  };
  for (const [key, url] of Object.entries(linkValues)) {
    if (url) links[key] = url;
    else delete links[key];
  }
  item.links = links;
  item.thumbnail = `./assets/images/thumbs/${id}.svg`;
  return item;
}

function renderList() {
  const query = slug($('#search').value);
  const items = query
    ? state.items.filter((item) => slug(`${item.titulo} ${item.autor}`).includes(query))
    : state.items;
  $('#result-line').textContent = `${items.length} ${items.length === 1 ? 'ficha' : 'fichas'}`;
  const list = $('#item-list');
  list.textContent = '';
  for (const item of items) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'item-row';
    if (state.current?.id === item.id) button.classList.add('is-active');
    const title = document.createElement('strong');
    title.textContent = item.titulo || item.id;
    const meta = document.createElement('span');
    meta.textContent = `${item.autor || 'Sem autoria'} · ${item.ano || '—'}`;
    button.append(title, meta);
    button.addEventListener('click', () => loadItem(item.id));
    list.append(button);
  }
}

async function loadIndex() {
  const response = await fetch('../data/indice.json', { cache: 'no-store' });
  if (!response.ok) throw new Error('Não foi possível carregar o índice do acervo.');
  state.items = await response.json();
  state.items.sort((a, b) => (b.ano || 0) - (a.ano || 0));
  renderList();
}

async function loadItem(id) {
  setStatus('Carregando ficha…');
  try {
    const item = await api(`/api/admin/item?id=${encodeURIComponent(id)}`);
    fillForm(item, false);
    renderList();
    setStatus('');
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function startNew() {
  const year = new Date().getFullYear();
  const id = uniqueId(`trabalho-${year}`);
  fillForm(
    {
      id,
      titulo: '',
      autor: '',
      ano: year,
      tipo: 'Dissertação',
      grau: 'Mestrado Acadêmico',
      resumo_idioma: 'por',
      tags: [],
      links: {},
    },
    true
  );
  renderList();
}

$('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  state.token = $('#token').value.trim();
  $('#login-note').textContent = 'Verificando acesso…';
  try {
    await api('/api/admin/session');
    sessionStorage.setItem(TOKEN_KEY, state.token);
    showApp(true);
    $('#login-note').textContent = '';
    await loadIndex();
  } catch (error) {
    $('#login-note').textContent = error.message || 'Token inválido.';
  }
});

$('#logout').addEventListener('click', () => {
  sessionStorage.removeItem(TOKEN_KEY);
  window.location.reload();
});

$('#search').addEventListener('input', renderList);
$('#new-item').addEventListener('click', startNew);
$('#field-autor').addEventListener('blur', () => {
  if (state.isNew && !$('#field-id').value.trim()) {
    $('#field-id').value = suggestedId();
  }
});
$('#field-ano').addEventListener('blur', () => {
  if (state.isNew && !$('#field-id').value.trim()) {
    $('#field-id').value = suggestedId();
  }
});

$('#field-id').addEventListener('input', () => {
  const id = $('#field-id').value;
  if (state.isNew) {
    $('#field-id').value = slug(id);
    $('#editor-title').textContent = 'Novo trabalho';
  }
});

$('#item-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const item = collect();
  if (!/^[a-z0-9][a-z0-9-]*$/.test(item.id)) {
    setStatus('ID inválido. Use letras minúsculas, números e hífens.', true);
    return;
  }
  const save = $('#save-item');
  save.disabled = true;
  setStatus('Salvando no GitHub…');
  try {
    const result = await api(`/api/admin/item?id=${encodeURIComponent(item.id)}`, {
      method: 'PUT',
      body: JSON.stringify(item),
    });
    const wasNew = state.isNew;
    state.current = item;
    state.isNew = false;
    $('#field-id').readOnly = true;
    $('#delete-item').hidden = false;
    const summary = { id: item.id, titulo: item.titulo, autor: item.autor, ano: item.ano };
    const existingIndex = state.items.findIndex((entry) => entry.id === item.id);
    if (existingIndex >= 0) state.items[existingIndex] = summary;
    else state.items.unshift(summary);
    state.items.sort((a, b) => (b.ano || 0) - (a.ano || 0));
    renderList();
    setStatus(
      `${wasNew ? 'Ficha criada' : 'Ficha salva'}. A reindexação automática será executada no GitHub.${
        result.commit ? ` Commit: ${result.commit}` : ''
      }`
    );
    $('#editor-title').textContent = item.titulo || item.id;
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    save.disabled = false;
  }
});

$('#delete-item').addEventListener('click', async () => {
  const id = state.current?.id;
  if (!id) return;
  if (!window.confirm(`Excluir definitivamente a ficha “${state.current.titulo || id}”?`)) return;
  setStatus('Excluindo…');
  try {
    const result = await api(`/api/admin/item?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
    state.items = state.items.filter((entry) => entry.id !== id);
    state.current = null;
    state.isNew = false;
    $('#item-form').hidden = true;
    $('#empty-editor').hidden = false;
    $('#editor-title').textContent = 'Acervo';
    $('#editor-mode').textContent = 'Ficha excluída';
    renderList();
    setStatus(
      `Ficha excluída. A reindexação automática será executada.${
        result.commit ? ` Commit: ${result.commit}` : ''
      }`
    );
  } catch (error) {
    setStatus(error.message, true);
  }
});

(async () => {
  if (!state.token) return;
  try {
    await api('/api/admin/session');
    showApp(true);
    await loadIndex();
  } catch {
    sessionStorage.removeItem(TOKEN_KEY);
  }
})();
