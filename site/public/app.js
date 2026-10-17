const app = document.getElementById('app');
const searchToggle = document.getElementById('search-toggle');
const headerSearch = document.getElementById('header-search');
const headerSearchForm = document.getElementById('header-search-form');
const headerSearchInput = document.getElementById('header-search-input');
const routeStatus = document.getElementById('route-status');
const footerUpdated = document.getElementById('footer-updated');
const menuToggle = document.querySelector('.tainacan-menu-toggle');
const menu = document.getElementById('menubelowHeader');

const SITE_TITLE = 'Repositório de Teses e Dissertações em Educação Estatística';
const MULTI_KEYS = ['ano', 'grau', 'tipo', 'regiao', 'area', 'foco', 'conteudo', 'nivel'];
const AREAS = [
  'Educação Matemática',
  'Ensino de Matemática',
  'Ensino de Ciências e Matemática',
  'Educação',
  'Estatística e Matemática',
  'Engenharia',
  'Psicologia',
  'Computação',
  'Administração',
  'Outros',
];
const REGIOES = ['Sudeste', 'Sul', 'Nordeste', 'Centro-Oeste', 'Norte'];
const GRAUS = ['Mestrado Acadêmico', 'Mestrado Profissional', 'Doutorado'];
const TIPOS = ['Dissertação', 'Tese'];
const FACET_LABELS = {
  ano: 'Ano',
  grau: 'Grau',
  tipo: 'Tipo',
  regiao: 'Região',
  estado: 'Estado',
  instituicao: 'Instituição',
  area: 'Área',
  foco: 'Foco temático',
  conteudo: 'Conteúdo',
  nivel: 'Nível de ensino',
};

const cache = new Map();
const state = {
  index: null,
  agregados: null,
  counts: null,
  route: null,
  q: '',
  filters: emptyFilters(),
  sortField: 'ano',
  sortDir: 'desc',
  page: 1,
  perPage: 20,
  mode: 'tabela',
  returnHash: '#/acervo',
  visibleIds: null,
  searchTimer: null,
  filtersCollapsed: false,
  mapMode: 'estado',
  mapa: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/* --- Utilidades ---------------------------------------------------------- */

function emptyFilters() {
  return {
    ano: new Set(),
    grau: new Set(),
    tipo: new Set(),
    regiao: new Set(),
    area: new Set(),
    foco: new Set(),
    conteudo: new Set(),
    nivel: new Set(),
    estado: '',
    instituicao: '',
  };
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => {
    switch (char) {
      case '&':
        return '&amp;';
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '"':
        return '&quot;';
      default:
        return '&#39;';
    }
  });
}

function norm(value) {
  return String(value ?? '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

function plural(count, singular, pluralForm) {
  return `${Number(count).toLocaleString('pt-BR')} ${Number(count) === 1 ? singular : pluralForm}`;
}

function pct(part, total) {
  if (!total) return 0;
  return Math.round((part / total) * 1000) / 10;
}

function announce(message) {
  if (!routeStatus) return;
  routeStatus.textContent = '';
  window.setTimeout(() => {
    routeStatus.textContent = message;
  }, 60);
}

function setMeta(title, description) {
  document.title = title && title !== SITE_TITLE ? `${title} · Observatório EE` : SITE_TITLE;
  const meta = document.querySelector('meta[name="description"]');
  if (meta && description) meta.setAttribute('content', description.slice(0, 180));
}

async function loadJSON(path) {
  if (cache.has(path)) return cache.get(path);
  const response = await fetch(path, { cache: 'no-cache' });
  if (!response.ok) {
    const error = new Error(
      response.status === 404 ? 'Registro não encontrado.' : 'Não foi possível carregar os dados.'
    );
    error.status = response.status;
    throw error;
  }
  const data = await response.json();
  cache.set(path, data);
  return data;
}

async function ensureData() {
  if (state.index) return;
  const [index, agregados, mapa] = await Promise.all([
    loadJSON('./data/indice.json'),
    loadJSON('./data/agregados.json'),
    loadJSON('./data/mapa-brasil.json').catch(() => null),
  ]);
  state.index = index;
  state.agregados = agregados;
  state.mapa = mapa;
  buildCounts();
  if (footerUpdated) {
    footerUpdated.textContent = `Dados de ${agregados.periodo.inicio}–${agregados.periodo.fim} · atualizado em ${new Date(
      agregados.atualizado_em
    ).toLocaleDateString('pt-BR')}`;
  }
}

function buildCounts() {
  const counts = {};
  for (const key of [...MULTI_KEYS, 'estado', 'instituicao']) {
    const map = new Map();
    for (const item of state.index) {
      const value = String(item[key] ?? '').trim();
      if (!value) continue;
      map.set(value, (map.get(value) || 0) + 1);
    }
    counts[key] = map;
  }
  state.counts = counts;
}

/* --- Roteamento ---------------------------------------------------------- */

function parseHash() {
  const raw = location.hash.replace(/^#/, '') || '/';
  const [pathPart, queryPart] = raw.split('?');
  const parts = pathPart.split('/').filter(Boolean);
  const params = new URLSearchParams(queryPart || '');
  if (parts[0] === 'item' && parts[1]) return { view: 'item', id: parts[1], params };
  if (parts[0] === 'acervo') return { view: 'acervo', params };
  if (parts[0] === 'panorama') return { view: 'panorama', params };
  if (parts[0] === 'sobre') return { view: 'sobre', params };
  return { view: 'home', params };
}

function readState(params) {
  state.q = params.get('q') || '';
  state.filters = emptyFilters();
  for (const key of MULTI_KEYS) {
    const raw = params.get(key);
    if (raw) {
      for (const value of raw.split('|').filter(Boolean)) state.filters[key].add(value);
    }
  }
  state.filters.estado = params.get('estado') || '';
  state.filters.instituicao = params.get('inst') || '';

  const ordem = params.get('ordem') || 'ano-desc';
  const [field, dir] = ordem.split('-');
  state.sortField = ['ano', 'titulo', 'autor', 'instituicao'].includes(field) ? field : 'ano';
  state.sortDir = dir === 'asc' ? 'asc' : 'desc';
  state.page = Math.max(1, Number(params.get('pagina')) || 1);
  state.perPage = [12, 20, 50].includes(Number(params.get('pp'))) ? Number(params.get('pp')) : 20;
  state.mode = params.get('modo') === 'cartoes' ? 'cartoes' : 'tabela';
}

function buildHash() {
  const params = new URLSearchParams();
  if (state.q) params.set('q', state.q);
  for (const key of MULTI_KEYS) {
    if (state.filters[key].size) params.set(key, [...state.filters[key]].join('|'));
  }
  if (state.filters.estado) params.set('estado', state.filters.estado);
  if (state.filters.instituicao) params.set('inst', state.filters.instituicao);
  const ordem = `${state.sortField}-${state.sortDir}`;
  if (ordem !== 'ano-desc') params.set('ordem', ordem);
  if (state.page > 1) params.set('pagina', String(state.page));
  if (state.perPage !== 20) params.set('pp', String(state.perPage));
  if (state.mode === 'cartoes') params.set('modo', 'cartoes');
  const query = params.toString();
  return `#/acervo${query ? `?${query}` : ''}`;
}

function replaceHash() {
  history.replaceState(null, '', buildHash());
}

function searchHash(query) {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  const suffix = params.toString();
  return `#/acervo${suffix ? `?${suffix}` : ''}`;
}

async function route() {
  closeFilters(false);
  closeMenu();
  closeHeaderSearch();
  const parsed = parseHash();
  state.route = parsed;
  readState(parsed.params);
  syncHeaderSearch();
  markNav(parsed.view);
  window.scrollTo(0, 0);

  try {
    await ensureData();
    if (parsed.view === 'home') renderHome();
    else if (parsed.view === 'acervo') renderAcervo();
    else if (parsed.view === 'panorama') renderPanorama();
    else if (parsed.view === 'sobre') renderAbout();
    else {
      renderLoading('Carregando registro…');
      await renderItem(parsed.id);
    }
    focusHeading();
  } catch (error) {
    renderError(error);
  }
}

function markNav(view) {
  const current = view === 'item' ? 'acervo' : view;
  $$('[data-nav]').forEach((link) => {
    if (link.dataset.nav === current) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
}

function focusHeading() {
  const heading = app.querySelector('h1, h2.tainacan-page-title');
  if (!heading) return;
  heading.setAttribute('tabindex', '-1');
  heading.focus({ preventScroll: true });
}

function renderLoading(message = 'Carregando…') {
  app.innerHTML = `<div class="tainacan-loading" role="status"><span class="tainacan-spinner" aria-hidden="true"></span><p>${esc(message)}</p></div>`;
}

function breadcrumb(items) {
  const parts = items.map((item, index) => {
    if (index === items.length - 1) return `<span aria-current="page">${esc(item.label)}</span>`;
    return `<a href="${esc(item.href)}">${esc(item.label)}</a>`;
  });
  return `<div class="tainacan-breadcrumb">${parts.join('<span class="sep">&gt;</span>')}</div>`;
}

/* --- Header -------------------------------------------------------------- */

function syncHeaderSearch() {
  if (headerSearchInput) headerSearchInput.value = state.route?.view === 'acervo' ? state.q : '';
}

function openHeaderSearch() {
  if (!headerSearch) return;
  headerSearch.hidden = false;
  searchToggle?.setAttribute('aria-expanded', 'true');
  headerSearchInput?.focus();
}

function closeHeaderSearch() {
  if (!headerSearch) return;
  headerSearch.hidden = true;
  searchToggle?.setAttribute('aria-expanded', 'false');
}

function closeMenu() {
  if (!menu || !menuToggle) return;
  menu.classList.remove('show');
  menuToggle.classList.add('collapsed');
  menuToggle.setAttribute('aria-expanded', 'false');
}

searchToggle?.addEventListener('click', () => {
  const open = searchToggle.getAttribute('aria-expanded') === 'true';
  if (open) closeHeaderSearch();
  else openHeaderSearch();
});

headerSearchForm?.addEventListener('submit', (event) => {
  event.preventDefault();
  const query = headerSearchInput.value.trim();
  location.hash = searchHash(query);
  closeHeaderSearch();
});

menuToggle?.addEventListener('click', () => {
  const open = menu?.classList.toggle('show');
  menuToggle.classList.toggle('collapsed', !open);
  menuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
});

/* --- Home ---------------------------------------------------------------- */

function renderHome() {
  const a = state.agregados;
  setMeta(
    'Início',
    'Repositório digital de teses e dissertações brasileiras em Educação Estatística (1984–2013).'
  );

  app.innerHTML = `
    <section class="home-hero" aria-labelledby="home-hero-title">
      <div class="home-hero__inner">
        <div class="home-hero__main">
          <span class="home-hero__kicker">Observatório da produção científica</span>
          <h1 class="home-hero__title" id="home-hero-title">
            Conhecer, preservar e<br />
            explorar a pesquisa em<br />
            Educação Estatística
          </h1>
          <p class="home-hero__lead">
            Um acervo dedicado às teses e dissertações brasileiras, à memória da pesquisa e à
            circulação do conhecimento.
          </p>
          <form class="home-search" id="home-search-form" role="search">
            <label class="sr-only" for="home-search-input">Pesquisar no acervo</label>
            <i class="tainacan-icon tainacan-icon-search" aria-hidden="true"></i>
            <input
              id="home-search-input"
              name="q"
              type="search"
              placeholder="Pesquise por título, autor ou assunto"
              autocomplete="off"
            />
            <button type="submit">Pesquisar <span aria-hidden="true">→</span></button>
          </form>
        </div>
        <aside class="home-hero__stats" aria-label="Números do acervo">
          <div class="home-stat">
            <strong>${a.total}</strong>
            <span>pesquisas catalogadas</span>
          </div>
          <div class="home-stat">
            <strong>${a.instituicoes}</strong>
            <span>instituições</span>
          </div>
          <div class="home-stat home-stat--small">
            <strong>${a.estados}</strong>
            <span>estados</span>
          </div>
        </aside>
      </div>
    </section>

    <div class="tainacan-page-wrap max-large margin-one-column home-content">
      <h2 class="home-section-title">Coleções</h2>
      <div class="tainacan-collection-card">
        <a class="collection-image" href="#/acervo" aria-label="Abrir o acervo"><img src="./assets/images/capa-colecao-card.svg" alt="" loading="lazy" /></a>
        <div>
          <h2><a href="#/acervo">Teses e Dissertações em Educação Estatística</a></h2>
          <p>
            Produção brasileira de teses e dissertações sobre Educação Estatística, organizada a
            partir da planilha de estado da arte. Inclui metadados sobre autoria, orientação,
            instituição, programa, nível de ensino, foco temático e conteúdo enfocado.
          </p>
          <div class="collection-meta">
            ${plural(a.total, 'item', 'itens')} · ${a.instituicoes} instituições · ${a.estados} estados
          </div>
          <div class="tainacan-item-links">
            <a href="#/acervo">Explorar o acervo</a>
            <a href="#/panorama">Ver o panorama</a>
            <a href="#/sobre">Sobre os dados</a>
          </div>
        </div>
      </div>

      <div class="home-note">
        <strong>Nota.</strong> O acervo foi organizado a partir do levantamento de estado da arte de
        Rodrigo Medeiros dos Santos (UNICAMP), com validação no Catálogo de Teses e Dissertações da
        CAPES e na BDTD. Os trabalhos não são hospedados neste site: cada registro leva ao
        repositório de origem, onde o arquivo pode ou não estar disponível.
        <a href="#/sobre">Saiba mais</a>.
      </div>
    </div>
  `;

  $('#home-search-form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const query = $('#home-search-input')?.value.trim() || '';
    location.hash = searchHash(query);
  });

  announce(`Página inicial. ${a.total} trabalhos catalogados.`);
}

/* --- Acervo -------------------------------------------------------------- */

function renderAcervo() {
  setMeta(
    'Acervo',
    'Explore teses e dissertações por ano, instituição, região, foco temático e conteúdo.'
  );

  app.innerHTML = `
    <div class="collection-banner-wrap">
      ${renderCollectionHero()}
    </div>
    <div class="tainacan-page-wrap max-large margin-one-column">
      ${breadcrumb([
        { label: 'Início', href: '#/' },
        { label: 'Acervo', href: '#/acervo' },
      ])}

      <div class="tainacan-faceted-layout${state.filtersCollapsed ? ' filters-collapsed' : ''}">
        <div class="tainacan-filters-scrim" data-close-filters hidden></div>
        <aside class="tainacan-filters" aria-label="Busca e filtros">
          <div class="tainacan-filters-top">
            <button
              type="button"
              class="tainacan-filter-panel-toggle"
              data-toggle-filters-panel
              aria-label="Recolher filtros"
              aria-expanded="${state.filtersCollapsed ? 'false' : 'true'}"
              aria-controls="filters-body"
            >
              <i class="tainacan-icon ${
                state.filtersCollapsed ? 'tainacan-icon-arrowright' : 'tainacan-icon-arrowleft'
              }" aria-hidden="true"></i>
            </button>
            <a class="tainacan-advanced-link" href="#/acervo" data-advanced-search>Busca avançada</a>
          </div>

          <div class="tainacan-filters-body" id="filters-body">
            <div class="tainacan-filters-head-mobile">
              <h2>Filtros</h2>
              <button type="button" class="tainacan-search-toggle" data-close-filters aria-label="Fechar filtros">
                <i class="tainacan-icon tainacan-icon-close" aria-hidden="true"></i>
              </button>
            </div>

            <div class="tainacan-facets-head">
              <h2>Filtros</h2>
              <button type="button" class="tainacan-collapse-all" data-collapse-all>Recolher todos</button>
            </div>
            <div id="facets">${renderFacets()}</div>
            <div class="tainacan-filter-actions">
              <button type="button" class="tainacan-button secondary small" data-clear-filters>Limpar</button>
              <button type="button" class="tainacan-button small" data-close-filters>Ver resultados</button>
            </div>
          </div>
        </aside>

        <section class="tainacan-results" aria-label="Resultados">
          <button type="button" class="tainacan-button secondary small tainacan-filter-toggle-mobile" data-open-filters>
            <i class="tainacan-icon tainacan-icon-filters" aria-hidden="true"></i> Filtros
            <span data-filter-count hidden></span>
          </button>

          <div class="tainacan-toolbar">
            <div class="tainacan-toolbar-group">
              <span class="tainacan-toolbar-label">Ordenação:</span>
              <select id="sort-field" aria-label="Campo de ordenação">
                <option value="ano">Data</option>
                <option value="titulo">Título</option>
                <option value="autor">Autor</option>
                <option value="instituicao">Instituição</option>
              </select>
              <div class="tainacan-sort-direction" role="group" aria-label="Direção da ordenação">
                <button type="button" data-sort-dir="asc" aria-label="Ordem crescente" aria-pressed="${
                  state.sortDir === 'asc'
                }"><i class="tainacan-icon tainacan-icon-sortascending" aria-hidden="true"></i></button>
                <button type="button" data-sort-dir="desc" aria-label="Ordem decrescente" aria-pressed="${
                  state.sortDir === 'desc'
                }"><i class="tainacan-icon tainacan-icon-sortdescending" aria-hidden="true"></i></button>
              </div>
            </div>

            <div class="tainacan-toolbar-group">
              <span class="tainacan-toolbar-label">Visualização:</span>
              <div class="tainacan-view-modes" role="group" aria-label="Modo de visualização">
                <button type="button" data-mode="tabela" aria-label="Tabela" aria-pressed="${
                  state.mode === 'tabela'
                }"><i class="tainacan-icon tainacan-icon-viewtable" aria-hidden="true"></i></button>
                <button type="button" data-mode="cartoes" aria-label="Cartões" aria-pressed="${
                  state.mode === 'cartoes'
                }"><i class="tainacan-icon tainacan-icon-viewcards" aria-hidden="true"></i></button>
              </div>
            </div>

            <span class="tainacan-result-count" id="result-count" role="status" aria-live="polite"></span>
          </div>

          <p class="acervo-access-note">
            <i class="tainacan-icon tainacan-icon-openurl" aria-hidden="true"></i>
            Os trabalhos não estão hospedados neste site. O ícone de acesso leva ao repositório de
            origem, onde o arquivo pode ou não estar disponível.
          </p>

          <div class="tainacan-active-filters" id="active-filters"></div>
          <div id="results"></div>
          <nav class="tainacan-pagination" id="pagination" aria-label="Paginação"></nav>
        </section>
      </div>
    </div>
  `;

  $('#collection-hero-search')?.addEventListener('submit', (event) => {
    event.preventDefault();
    state.q = $('#collection-hero-search-input')?.value.trim() || '';
    state.page = 1;
    syncHeaderSearch();
    replaceHash();
    renderResults();
  });

  $('#sort-field').value = state.sortField;
  bindCollectionEvents();
  renderResults();
}

function renderCollectionHero() {
  const a = state.agregados;
  return `
    <section class="collection-banner" aria-labelledby="collection-banner-title">
      <div class="collection-banner__inner">
        <div class="collection-banner__main">
          <span class="collection-banner__kicker">Acervo digital</span>
          <h1 class="collection-banner__title" id="collection-banner-title">
            Teses e dissertações em<br />
            Educação Estatística
          </h1>
          <p class="collection-banner__lead">
            Produção acadêmica brasileira organizada para consulta, preservação e pesquisa.
          </p>
          <form class="collection-banner__search" id="collection-hero-search" role="search">
            <label class="sr-only" for="collection-hero-search-input">Buscar no acervo</label>
            <input
              id="collection-hero-search-input"
              type="search"
              value="${esc(state.q)}"
              placeholder="Buscar por título, autor ou assunto"
              autocomplete="off"
            />
            <button type="submit">Buscar <span aria-hidden="true">→</span></button>
          </form>
        </div>
        <aside class="collection-banner__stats" aria-label="Números do acervo">
          <div class="collection-banner__stat collection-banner__stat--large">
            <strong>${a.total}</strong>
            <span>trabalhos</span>
          </div>
          <div class="collection-banner__stat">
            <strong>${a.instituicoes}</strong>
            <span>instituições</span>
          </div>
          <div class="collection-banner__stat">
            <strong>${a.estados}</strong>
            <span>estados</span>
          </div>
        </aside>
      </div>
    </section>
  `;
}

function facetValues(key) {
  const counts = state.counts[key] || new Map();
  const values = [...counts.entries()].map(([value, count]) => ({ value, count }));
  const order = {
    grau: GRAUS,
    tipo: TIPOS,
    regiao: REGIOES,
    area: AREAS,
  }[key];

  if (order) {
    return order.filter((value) => counts.has(value)).map((value) => ({ value, count: counts.get(value) }));
  }
  if (key === 'ano') return values.sort((a, b) => Number(b.value) - Number(a.value));
  return values.sort((a, b) => {
    if (a.value === 'Não informado') return 1;
    if (b.value === 'Não informado') return -1;
    return b.count - a.count || a.value.localeCompare(b.value, 'pt-BR');
  });
}

function checkboxFacet(key, open = false) {
  const values = facetValues(key);
  if (!values.length) return '';
  const selected = state.filters[key];
  return `
    <details class="tainacan-facet" ${open ? 'open' : ''}>
      <summary>
        <i class="tainacan-icon tainacan-icon-plus icon-plus" aria-hidden="true"></i>
        <i class="tainacan-icon tainacan-icon-minus icon-minus" aria-hidden="true"></i>
        ${esc(FACET_LABELS[key])}
      </summary>
      <div class="tainacan-facet-values">
        ${values
          .map(
            (entry) => `
              <label>
                <input type="checkbox" data-filter="${key}" value="${esc(entry.value)}" ${
                  selected.has(String(entry.value)) ? 'checked' : ''
                } />
                <span>${esc(entry.value)}</span>
                <span class="facet-count">${entry.count}</span>
              </label>
            `
          )
          .join('')}
      </div>
    </details>
  `;
}

function selectFacet(key) {
  const values = [...(state.counts[key] || new Map()).entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => a.value.localeCompare(b.value, 'pt-BR'));
  if (!values.length) return '';
  const selected = state.filters[key];
  return `
    <details class="tainacan-facet">
      <summary>
        <i class="tainacan-icon tainacan-icon-plus icon-plus" aria-hidden="true"></i>
        <i class="tainacan-icon tainacan-icon-minus icon-minus" aria-hidden="true"></i>
        ${esc(FACET_LABELS[key])}
      </summary>
      <select data-filter-select="${key}" aria-label="${esc(FACET_LABELS[key])}">
        <option value="">Todos</option>
        ${values
          .map(
            (entry) =>
              `<option value="${esc(entry.value)}" ${selected === entry.value ? 'selected' : ''}>${esc(
                entry.value
              )} (${entry.count})</option>`
          )
          .join('')}
      </select>
    </details>
  `;
}

function renderFacets() {
  return `
    ${checkboxFacet('ano', true)}
    ${checkboxFacet('grau', true)}
    ${checkboxFacet('tipo', true)}
    ${checkboxFacet('regiao', true)}
    ${selectFacet('estado')}
    ${selectFacet('instituicao')}
    ${checkboxFacet('area')}
    ${checkboxFacet('foco')}
    ${checkboxFacet('conteudo')}
    ${checkboxFacet('nivel')}
  `;
}

function activeFilterEntries() {
  const entries = [];
  if (state.q.trim()) entries.push({ type: 'q', key: 'q', value: state.q.trim() });
  for (const key of MULTI_KEYS) {
    for (const value of state.filters[key]) entries.push({ type: 'multi', key, value });
  }
  if (state.filters.estado) entries.push({ type: 'select', key: 'estado', value: state.filters.estado });
  if (state.filters.instituicao) {
    entries.push({ type: 'select', key: 'instituicao', value: state.filters.instituicao });
  }
  return entries;
}

function matches(item) {
  const q = norm(state.q);
  if (q && !item.busca_norm.includes(q)) return false;
  for (const key of MULTI_KEYS) {
    if (state.filters[key].size && !state.filters[key].has(String(item[key]))) return false;
  }
  if (state.filters.estado && item.estado !== state.filters.estado) return false;
  if (state.filters.instituicao && item.instituicao !== state.filters.instituicao) return false;
  return true;
}

function currentItems() {
  const collator = new Intl.Collator('pt-BR', { sensitivity: 'base' });
  const items = state.index.filter(matches);
  const direction = state.sortDir === 'asc' ? 1 : -1;
  const field = state.sortField;
  items.sort((a, b) => {
    if (field === 'ano') return ((a.ano || 0) - (b.ano || 0)) * direction;
    if (field === 'titulo') return collator.compare(a.titulo, b.titulo) * direction;
    if (field === 'autor') return collator.compare(a.autor, b.autor) * direction;
    if (field === 'instituicao') {
      return (
        (collator.compare(a.instituicao, b.instituicao) || (a.ano || 0) - (b.ano || 0)) *
        direction
      );
    }
    return 0;
  });
  return items;
}

function renderResults() {
  if (!state.index) return;
  const items = currentItems();
  state.visibleIds = items.map((item) => item.id);
  const totalPages = Math.max(1, Math.ceil(items.length / state.perPage));
  state.page = Math.min(Math.max(1, state.page), totalPages);
  const start = (state.page - 1) * state.perPage;
  const pageItems = items.slice(start, start + state.perPage);
  const active = activeFilterEntries();

  state.returnHash = buildHash();
  if (location.hash !== buildHash()) replaceHash();

  const count = $('#result-count');
  if (count) {
    count.textContent = `${plural(items.length, 'item', 'itens')}${
      state.q.trim() ? ` para “${state.q.trim()}”` : ''
    }`;
  }

  $$('[data-mode]').forEach((button) => {
    button.setAttribute('aria-pressed', button.dataset.mode === state.mode ? 'true' : 'false');
  });
  $$('[data-sort-dir]').forEach((button) => {
    button.setAttribute(
      'aria-pressed',
      button.dataset.sortDir === state.sortDir ? 'true' : 'false'
    );
  });

  renderActiveFilters(active);
  updateFilterBadge(active.length);

  const results = $('#results');
  if (!results) return;

  if (!pageItems.length) {
    results.innerHTML = `
      <div class="tainacan-empty">
        <i class="tainacan-icon tainacan-icon-search" aria-hidden="true"></i>
        <h2>Nenhum item encontrado</h2>
        <p>Não encontramos trabalhos com os termos e filtros atuais.</p>
        <button type="button" class="tainacan-button small" data-clear-filters>Limpar busca e filtros</button>
      </div>
    `;
  } else if (state.mode === 'cartoes') {
    results.innerHTML = `<div class="tainacan-cards">${pageItems.map(renderCard).join('')}</div>`;
  } else {
    results.innerHTML = renderTable(pageItems);
  }

  renderPagination(items.length, totalPages);
  announce(`${items.length} itens encontrados. Página ${state.page} de ${totalPages}.`);
}

function renderActiveFilters(entries) {
  const container = $('#active-filters');
  if (!container) return;
  if (!entries.length) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = `
    ${entries
      .map((entry) => {
        const label =
          entry.type === 'q'
            ? `Busca: “${entry.value}”`
            : `${FACET_LABELS[entry.key]}: ${entry.value}`;
        return `<button type="button" class="tainacan-filter-chip" data-remove-filter="${entry.key}" data-value="${esc(
          entry.value
        )}" aria-label="Remover filtro ${esc(label)}">${esc(label)} <span aria-hidden="true">×</span></button>`;
      })
      .join('')}
    <button type="button" class="tainacan-filter-chip" data-clear-filters>Limpar tudo ×</button>
  `;
}

function updateFilterBadge(count) {
  $$('[data-filter-count]').forEach((badge) => {
    badge.textContent = count ? `(${count})` : '';
    badge.hidden = count === 0;
  });
}

function renderTable(items) {
  return `
    <div class="tainacan-table-wrap">
      <table class="tainacan-table">
        <thead>
          <tr>
            <th class="col-thumb">Miniatura</th>
            <th>Título</th>
            <th class="col-hide-mobile">Autor</th>
            <th class="col-year">Ano</th>
            <th class="col-hide-mobile">Instituição</th>
            <th class="col-hide-mobile">Área</th>
            <th class="col-link col-hide-mobile">Acesso</th>
          </tr>
        </thead>
        <tbody>
          ${items
            .map(
              (item) => `
                <tr>
                  <td><img class="item-thumb" src="${thumbSrc(item)}" alt="" loading="lazy" onerror="this.src='./assets/images/thumbnail_placeholder.png'" /></td>
                  <td><a href="#/item/${encodeURIComponent(item.id)}">${esc(item.titulo)}</a></td>
                  <td class="col-hide-mobile">${esc(item.autor)}</td>
                  <td class="col-year">${item.ano || '—'}</td>
                  <td class="col-hide-mobile">${esc(item.instituicao)}</td>
                  <td class="col-hide-mobile">${esc(item.area)}</td>
                  <td class="col-link col-hide-mobile">
                    <a
                      class="record-link${item.link ? '' : ' record-link--search'}"
                      href="${esc(
                        item.link ||
                          `https://scholar.google.com/scholar?q=${encodeURIComponent(
                            `"${item.titulo}"`
                          )}`
                      )}"
                      target="_blank"
                      rel="noopener noreferrer"
                      title="${item.link ? 'Abrir registro' : 'Buscar no Google Scholar'}"
                      aria-label="${
                        item.link
                          ? `Abrir registro de ${esc(item.titulo)}`
                          : `Buscar no Google Scholar: ${esc(item.titulo)}`
                      }"
                    >
                      <i class="tainacan-icon ${
                        item.link ? 'tainacan-icon-openurl' : 'tainacan-icon-search'
                      }" aria-hidden="true"></i>
                    </a>
                  </td>
                </tr>
              `
            )
            .join('')}
        </tbody>
      </table>
    </div>
  `;
}

function thumbSrc(item) {
  const path = item.thumbnail || `./assets/images/thumbs/${encodeURIComponent(item.id)}.svg`;
  return `${path}?v=20261017-4`;
}

function renderCard(item) {
  return `
    <a class="tainacan-card" href="#/item/${encodeURIComponent(item.id)}">
      <div class="card-image">
        <img src="${thumbSrc(item)}" alt="" loading="lazy" onerror="this.src='./assets/images/thumbnail_placeholder.png'" />
      </div>
      <h3>${esc(item.titulo)}</h3>
      <div class="card-meta">
        <span class="card-author">${esc(item.autor)} · ${item.ano || '—'}</span>
        <span class="card-institution">${esc(item.instituicao)}</span>
      </div>
      <div class="card-description">${esc(item.resumo)}</div>
    </a>
  `;
}

function renderPagination(totalItems, totalPages) {
  const container = $('#pagination');
  if (!container) return;
  const from = totalItems ? (state.page - 1) * state.perPage + 1 : 0;
  const to = Math.min(state.page * state.perPage, totalItems);

  const pages = new Set([1, totalPages, state.page]);
  for (let offset = 1; offset <= 2; offset++) {
    if (state.page - offset > 1) pages.add(state.page - offset);
    if (state.page + offset < totalPages) pages.add(state.page + offset);
  }
  const sorted = [...pages].sort((a, b) => a - b);
  const numbers = [];
  let previous = 0;
  for (const page of sorted) {
    if (previous && page - previous > 1) numbers.push('<span class="sep">…</span>');
    numbers.push(
      `<button type="button" data-page="${page}" ${
        page === state.page ? 'aria-current="page"' : ''
      } aria-label="Página ${page}">${page}</button>`
    );
    previous = page;
  }

  container.innerHTML = `
    <span>Mostrando itens ${from} a ${to} de ${totalItems}.</span>
    <span class="spacer"></span>
    <label>Itens por página:
      <select id="per-page" aria-label="Itens por página">
        ${[12, 20, 50].map((value) => `<option value="${value}" ${state.perPage === value ? 'selected' : ''}>${value}</option>`).join('')}
      </select>
    </label>
    <label>Ir para página:
      <select id="go-to-page" aria-label="Ir para página">
        ${Array.from({ length: totalPages }, (_, index) => index + 1)
          .map((page) => `<option value="${page}" ${state.page === page ? 'selected' : ''}>${page}</option>`)
          .join('')}
      </select>
    </label>
    <div class="tainacan-page-numbers">
      <button type="button" data-page="${state.page - 1}" ${state.page <= 1 ? 'disabled' : ''} aria-label="Página anterior">
        <i class="tainacan-icon tainacan-icon-arrowleft" aria-hidden="true"></i>
      </button>
      ${numbers.join('')}
      <button type="button" data-page="${state.page + 1}" ${
        state.page >= totalPages ? 'disabled' : ''
      } aria-label="Próxima página">
        <i class="tainacan-icon tainacan-icon-arrowright" aria-hidden="true"></i>
      </button>
    </div>
  `;
}

function bindCollectionEvents() {
  $('[data-toggle-filters-panel]')?.addEventListener('click', (event) => {
    state.filtersCollapsed = !state.filtersCollapsed;
    const layout = $('.tainacan-faceted-layout');
    layout?.classList.toggle('filters-collapsed', state.filtersCollapsed);
    const button = event.currentTarget;
    button.setAttribute('aria-expanded', String(!state.filtersCollapsed));
    button.setAttribute('aria-label', state.filtersCollapsed ? 'Expandir filtros' : 'Recolher filtros');
    const icon = button.querySelector('.tainacan-icon');
    if (icon) {
      icon.classList.toggle('tainacan-icon-arrowleft', !state.filtersCollapsed);
      icon.classList.toggle('tainacan-icon-arrowright', state.filtersCollapsed);
    }
  });

  const search = $('#collection-search') || $('#collection-hero-search-input');
  let timer;
  const run = () => {
    state.q = search?.value.trim() || '';
    state.page = 1;
    syncHeaderSearch();
    renderResults();
  };
  search?.addEventListener('input', () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(run, 250);
  });
  search?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      run();
    }
  });
  $('[data-search-submit]')?.addEventListener('click', run);
  $('[data-advanced-search]')?.addEventListener('click', (event) => {
    event.preventDefault();
    search?.focus();
  });
  $('[data-collapse-all]')?.addEventListener('click', (event) => {
    const details = $$('.tainacan-facet');
    const anyOpen = details.some((detail) => detail.open);
    details.forEach((detail) => {
      detail.open = !anyOpen;
    });
    event.currentTarget.textContent = anyOpen ? 'Expandir todos' : 'Recolher todos';
  });
  $('[data-share]')?.addEventListener('click', async () => {
    const shareData = { title: document.title, url: location.href };
    try {
      if (navigator.share) await navigator.share(shareData);
      else {
        await navigator.clipboard.writeText(location.href);
        announce('Link copiado para a área de transferência.');
      }
    } catch {
      /* compartilhamento cancelado */
    }
  });
}

/* --- Item ---------------------------------------------------------------- */

async function renderItem(id) {
  const item = await loadJSON(`./data/itens/${encodeURIComponent(id)}.json`);
  setMeta(item.titulo, item.problema || `${item.tipo} de ${item.autor} (${item.ano}).`);

  const abstract = abstractEntry(item);
  const keywords = itemKeywords(item);
  app.innerHTML = `
    <div class="tainacan-page-wrap max-large margin-one-column">
      ${breadcrumb([
        { label: 'Início', href: '#/' },
        { label: 'Acervo', href: state.returnHash },
        { label: 'Item', href: '#' },
      ])}

      <div class="tainacan-page-title-row">
        <h1 class="tainacan-item-title">${esc(item.titulo)}</h1>
        <a class="tainacan-back-link" href="${esc(state.returnHash)}">Voltar</a>
      </div>

      <div class="tainacan-item-meta">
        ${item.ano || 'Sem ano'} · ${esc(item.autor)} · ${esc(item.tipo)} · ${esc(item.grau)}
      </div>

      <section class="tainacan-item-section" aria-labelledby="metadata-title">
        <h2 id="metadata-title">Metadados</h2>
        <dl class="tainacan-metadata-grid">
          ${metadataEntry('Autor', item.autor)}
          ${metadataEntry('Ano', item.ano)}
          ${metadataEntry('Tipo', item.tipo)}
          ${metadataEntry('Grau', item.grau)}
          ${metadataEntry('Instituição', item.instituicao || item.instituicao_capes)}
          ${metadataEntry(
            'Cidade / UF',
            [item.cidade || item.cidade_capes, item.estado].filter(Boolean).join(', ')
          )}
          ${metadataEntry('Região', item.regiao)}
          ${metadataEntry('Orientação', item.orientador)}
          ${metadataEntry('Programa', item.programa || item.programa_capes)}
          ${metadataEntry('Área', item.area)}
          ${metadataEntry('Nível de ensino', item.nivel)}
          ${metadataEntry('Foco temático', item.foco)}
          ${metadataEntry('Conteúdo', item.conteudo)}
        </dl>
      </section>

      <section class="tainacan-text-block" aria-labelledby="resumo-title">
        <h2 id="resumo-title">Resumo</h2>
        ${
          abstract.text
            ? `<p>${esc(abstract.text)}</p>`
            : '<p class="tainacan-text-empty">Resumo não localizado no registro.</p>'
        }
        ${
          abstract.fromProblem
            ? '<p class="tainacan-text-note">Resumo não localizado no repositório; texto a partir dos objetivos da pesquisa.</p>'
            : ''
        }
        ${
          abstract.english
            ? '<p class="tainacan-text-note">Resumo em inglês</p>'
            : ''
        }
      </section>

      <section class="tainacan-text-block" aria-labelledby="keywords-title">
        <h2 id="keywords-title">Palavras-chave</h2>
        ${
          keywords.length
            ? `<ul class="tainacan-keywords">${keywords.map((word) => `<li>${esc(word)}</li>`).join('')}</ul>`
            : '<p class="tainacan-text-empty">Não informadas no registro.</p>'
        }
      </section>

    </div>
  `;

  announce(`Registro: ${item.titulo}, ${item.autor}, ${item.ano}.`);
}

function metadataEntry(label, value) {
  return `<div class="tainacan-metadata-entry"><dt>${esc(label)}</dt><dd>${esc(
    value || 'Não informado'
  )}</dd></div>`;
}

function abstractEntry(item) {
  const english = item.resumo_idioma === 'eng';
  const resumo = String(item.resumo || '').trim();
  if (resumo) return { text: resumo, fromProblem: false, english };

  const resumoBdtd = String(item.resumo_bdtd || '').trim();
  if (resumoBdtd) return { text: resumoBdtd, fromProblem: false, english };

  const problema = String(item.problema || '').replace(/\s+/g, ' ').trim();
  if (problema) return { text: problema, fromProblem: true, english };

  return { text: '', fromProblem: false, english: false };
}

function itemKeywords(item) {
  const clean = (words) => {
    const seen = new Set();
    return words
      .map((word) => String(word ?? '').replace(/\s+/g, ' ').trim())
      .filter((word) => word && !/^não possui/i.test(word))
      .filter((word) => {
        const key = norm(word);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 24);
  };

  if (Array.isArray(item.tags) && item.tags.length) return clean(item.tags);

  const bdtd = clean(String(item.palavras_chave_bdtd || '').split(';'));
  if (bdtd.length) return bdtd;

  const planilha = String(item.palavras_chave || '');
  if (!planilha.trim() || /não possui/i.test(planilha)) return [];
  return clean(planilha.split(/[;,.]/));
}

/* --- Panorama ------------------------------------------------------------ */

const REGION_ORDER = ['Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul'];
const REGION_COLORS = {
  Norte: '#2E7D89',
  Nordeste: '#C08A2E',
  'Centro-Oeste': '#6F8F55',
  Sudeste: '#8C5A7A',
  Sul: '#4F6FA8',
};

function renderBrazilMap(a) {
  const mapa = state.mapa;
  if (!mapa?.states?.length) return '';

  const counts = new Map(a.por_estado.map((entry) => [entry.rotulo, entry.total]));
  const maxState = Math.max(...counts.values(), 1);
  const byRegion = new Map();
  for (const uf of mapa.states) {
    const count = counts.get(uf.nome) || 0;
    const region = byRegion.get(uf.regiao) || { total: 0, x: 0, y: 0, states: 0 };
    region.total += count;
    if (count > 0) {
      region.x += uf.cx * count;
      region.y += uf.cy * count;
      region.states += count;
    }
    byRegion.set(uf.regiao, region);
  }

  const mode = state.mapMode === 'regiao' ? 'regiao' : 'estado';
  const paths = mapa.states
    .map((uf) => {
      const count = counts.get(uf.nome) || 0;
      const fill = mode === 'regiao' ? REGION_COLORS[uf.regiao] || '#CFE0E2' : '#D5E3E5';
      return `<path d="${uf.path}" class="map-state" data-uf="${uf.uf}" fill="${fill}" fill-opacity="${
        mode === 'regiao' ? '0.85' : '1'
      }" stroke="#FFFFFF" stroke-width="1.6"><title>${esc(uf.nome)}: ${count} ${
        count === 1 ? 'trabalho' : 'trabalhos'
      }</title></path>`;
    })
    .join('');

  const labels = mapa.states
    .map((uf) => `<text x="${uf.cx}" y="${uf.cy}" class="map-label" text-anchor="middle">${uf.uf}</text>`)
    .join('');

  const bubbles =
    mode === 'estado'
      ? mapa.states
          .map((uf) => {
            const count = counts.get(uf.nome) || 0;
            if (!count) return '';
            const radius = 3 + Math.sqrt(count / maxState) * 23;
            return `<circle cx="${uf.cx}" cy="${uf.cy}" r="${radius.toFixed(1)}" class="map-bubble${
              count === maxState ? ' map-bubble--max' : ''
            }" data-uf="${uf.uf}" style="fill:${
              count === maxState ? '#D96A3A' : REGION_COLORS[uf.regiao]
            };fill-opacity:0.85"><title>${esc(uf.nome)}: ${count} trabalhos</title></circle>`;
          })
          .join('')
      : [...byRegion.entries()]
          .map(([region, entry]) => {
            if (!entry.states) return '';
            const x = entry.x / entry.states;
            const y = entry.y / entry.states;
            const radius = 4 + Math.sqrt(entry.total / maxState) * 23;
            return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${radius.toFixed(
              1
            )}" class="map-bubble map-bubble--region" style="fill:#FFFFFF;fill-opacity:1;stroke:${REGION_COLORS[region]};stroke-width:2.5"><title>${esc(
              region
            )}: ${entry.total} trabalhos</title></circle><text x="${x.toFixed(1)}" y="${(
              y + radius + 12
            ).toFixed(1)}" class="map-region-label" text-anchor="middle">${esc(region)}</text>`;
          })
          .join('');

  const regionSummary = REGION_ORDER.map((region) => {
    const entry = a.por_regiao.find((row) => row.rotulo === region) || { total: 0 };
    const percent = a.total ? ((entry.total / a.total) * 100).toFixed(1).replace('.', ',') : '0,0';
    const maxRegion = Math.max(...a.por_regiao.map((row) => row.total), 1);
    return `<li>
      <span class="region-summary-name"><i class="region-dot" style="--region-color:${REGION_COLORS[region]}"></i>${region}</span>
      <strong>${entry.total} ${entry.total === 1 ? 'trabalho' : 'trabalhos'}</strong>
      <span class="region-summary-percent">${percent}%</span>
      <span class="region-summary-track"><span style="width:${pct(entry.total, maxRegion)}%"></span></span>
    </li>`;
  }).join('');

  const stateRows = a.por_estado
    .map((entry) => {
      const uf = mapa.states.find((state) => state.nome === entry.rotulo)?.uf || '—';
      return `<tr><td>${uf}</td><td>${esc(entry.rotulo)}</td><td>${entry.total}</td></tr>`;
    })
    .join('');

  return `
    <section class="panorama-map-section" aria-labelledby="map-title">
      <div class="panorama-map-head">
        <div>
          <h2 id="map-title">Distribuição dos trabalhos no Brasil</h2>
          <p>Visualize a concentração de teses e dissertações em Educação Estatística por região ou estado.</p>
        </div>
        <div class="map-tabs" role="group" aria-label="Modo de visualização do mapa">
          <button type="button" data-map-mode="regiao" aria-pressed="${mode === 'regiao'}">Por região</button>
          <button type="button" data-map-mode="estado" aria-pressed="${mode === 'estado'}">Por estado</button>
        </div>
      </div>

      <div class="brazil-map-wrap">
        <svg class="brazil-map${mode === 'regiao' ? ' brazil-map--regiao' : ''}" viewBox="${mapa.viewBox}" role="img" aria-label="Mapa do Brasil com a distribuição dos trabalhos por ${
          mode === 'regiao' ? 'região' : 'estado'
        }">
          <g class="map-paths">${paths}</g>
          <g class="map-labels">${labels}</g>
          <g class="map-bubbles">${bubbles}</g>
        </svg>
        <div class="map-legend" aria-label="Legenda do mapa">
          <strong>Número de trabalhos</strong>
          <div class="map-legend-sizes">
            <span><i style="--size:4px"></i>1–2</span>
            <span><i style="--size:8px"></i>3–10</span>
            <span><i style="--size:14px"></i>11–30</span>
            <span><i style="--size:22px"></i>&gt; 30</span>
          </div>
          <div class="map-region-legend">
            ${REGION_ORDER.map(
              (region) =>
                `<span><i style="--region-color:${REGION_COLORS[region]}"></i>${region}</span>`
            ).join('')}
          </div>
          <p>Quanto maior a bolha, maior a concentração. A bolha laranja destaca o maior total.</p>
        </div>
      </div>

      <div class="region-summary">
        <h3>Trabalhos por região</h3>
        <p>Número de teses e dissertações em cada região do Brasil.</p>
        <ul class="region-summary-grid">${regionSummary}</ul>
        <details class="map-data-table">
          <summary>Ver os dados por estado</summary>
          <table class="tainacan-table">
            <thead><tr><th>UF</th><th>Estado</th><th>Total</th></tr></thead>
            <tbody>${stateRows}</tbody>
          </table>
        </details>
      </div>
    </section>
  `;
}

function renderPanorama() {
  const a = state.agregados;
  setMeta('Panorama', 'Séries e distribuições do acervo por ano, grau, região, conteúdo e instituição.');

  const maxYear = Math.max(...a.por_ano.map((entry) => entry.total), 1);
  const labelYears = new Set([1984, 1990, 1995, 2000, 2005, 2010, 2013]);
  const bars = a.por_ano
    .map((entry) => {
      const height = Math.max(1, Math.round((entry.total / maxYear) * 100));
      return `<span class="timeline-bar${entry.total === 0 ? ' is-zero' : ''}" style="--v:${height}" title="${entry.ano}: ${entry.total}" aria-label="${entry.ano}: ${entry.total}"></span>`;
    })
    .join('');
  const labels = a.por_ano
    .map((entry) => `<span>${labelYears.has(entry.ano) ? entry.ano : ''}</span>`)
    .join('');

  const grauValue = (label) => a.por_grau.find((entry) => entry.rotulo === label)?.total || 0;
  const ma = grauValue('Mestrado Acadêmico');
  const mp = grauValue('Mestrado Profissional');
  const dou = grauValue('Doutorado');

  app.innerHTML = `
    <div class="tainacan-page-wrap max-large margin-one-column">
      ${breadcrumb([
        { label: 'Início', href: '#/' },
        { label: 'Panorama', href: '#/panorama' },
      ])}
      <h1 class="tainacan-page-title">Panorama do acervo</h1>
      <p class="tainacan-lead">
        Distribuição dos ${a.total} trabalhos por ano, grau, região, conteúdo enfocado, foco
        temático e instituição. Os números refletem o recorte de ${a.periodo.inicio} a
        ${a.periodo.fim}. Os gráficos são recalculados a partir do acervo sempre que novos
        trabalhos são inseridos.
      </p>

      <div class="tainacan-panorama">
        ${renderBrazilMap(a)}

        <section class="tainacan-panorama-section">
          <h2>Produção por ano</h2>
          <div style="overflow-x:auto">
            <div class="timeline" role="img" aria-label="Produção por ano">${bars}</div>
            <div class="timeline-labels" aria-hidden="true">${labels}</div>
          </div>
          <details style="margin-top:.8rem;font-size:.8125rem">
            <summary>Ver os dados do gráfico</summary>
            <table class="tainacan-table" style="margin-top:.6rem">
              <thead><tr><th>Ano</th><th>Total</th></tr></thead>
              <tbody>${a.por_ano.map((entry) => `<tr><td>${entry.ano}</td><td>${entry.total}</td></tr>`).join('')}</tbody>
            </table>
          </details>
        </section>

        <div class="tainacan-panorama-grid">
          <section class="tainacan-panorama-section panorama-section--grau">
            <h2>Grau</h2>
            <div class="panorama-donut">
              <div class="donut" style="--a:${pct(ma, a.total)};--b:${pct(mp, a.total)}" role="img" aria-label="Mestrado acadêmico: ${ma}; mestrado profissional: ${mp}; doutorado: ${dou}">
                <span>${a.total}<small>trabalhos</small></span>
              </div>
              <ul class="panorama-legend">
                <li><span class="dot" style="--dot:#174B57"></span><span>Mestrado acadêmico</span><strong>${ma}</strong></li>
                <li><span class="dot" style="--dot:#2E7D89"></span><span>Mestrado profissional</span><strong>${mp}</strong></li>
                <li><span class="dot" style="--dot:#8FB3B9"></span><span>Doutorado</span><strong>${dou}</strong></li>
              </ul>
            </div>
          </section>

          <section class="tainacan-panorama-section panorama-section--conteudo">
            <h2>Conteúdo enfocado</h2>
            ${renderPanoramaBars(a.por_conteudo, 'green', null)}
          </section>

          <section class="tainacan-panorama-section panorama-section--foco">
            <h2>Foco temático</h2>
            ${renderPanoramaBars(a.por_foco, 'mustard', 10)}
          </section>

          <section class="tainacan-panorama-section panorama-section--instituicoes">
            <h2>Instituições com mais trabalhos</h2>
            <ol class="panorama-rank">
              ${a.top_instituicoes
                .map(
                  (entry, index) => `
                    <li><span class="n">${String(index + 1).padStart(2, '0')}</span><span class="name" title="${esc(
                      entry.nome
                    )}">${esc(entry.nome)}</span><strong>${entry.total}</strong></li>
                  `
                )
                .join('')}
            </ol>
          </section>

        </div>
      </div>
    </div>
  `;

  $$('[data-map-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      if (state.mapMode === button.dataset.mapMode) return;
      state.mapMode = button.dataset.mapMode;
      renderPanorama();
    });
  });

  announce('Página de panorama do acervo.');
}

function renderPanoramaBars(series, tone = '', limit = 10) {
  const max = Math.max(...series.map((entry) => entry.total), 1);
  const entries = limit ? series.slice(0, limit) : series;
  return `
    <ul class="panorama-bars ${tone}">
      ${entries
        .map(
          (entry) => `
            <li>
              <span class="bar-top"><span>${esc(entry.rotulo)}</span><strong>${entry.total}</strong></span>
              <span class="bar-track" aria-hidden="true"><span class="bar-fill" style="--pct:${pct(
                entry.total,
                max
              )}"></span></span>
            </li>
          `
        )
        .join('')}
    </ul>
  `;
}

/* --- Sobre --------------------------------------------------------------- */

function renderAbout() {
  const a = state.agregados;
  const semFoco = a.por_foco.find((entry) => entry.rotulo === 'Não informado')?.total || 0;
  const comFoco = a.total - semFoco;
  const tipoLabels = { Dissertação: 'dissertações', Tese: 'teses' };
  const focosOrdenados = [...a.por_foco].sort((x, y) => {
    const cx = focoCode(x.rotulo);
    const cy = focoCode(y.rotulo);
    if (cx === '—') return 1;
    if (cy === '—') return -1;
    return Number(cx) - Number(cy);
  });

  setMeta('Sobre os dados', 'Metodologia, códigos, limitações e downloads do repositório.');

  app.innerHTML = `
    <div class="tainacan-page-wrap max-large margin-one-column">
      ${breadcrumb([
        { label: 'Início', href: '#/' },
        { label: 'Sobre os dados', href: '#/sobre' },
      ])}
      <h1 class="tainacan-page-title">Sobre este repositório</h1>

      <div class="tainacan-prose">
        <h2>O que está no acervo</h2>
        <p>
          São ${a.total} registros: ${a.por_tipo
            .map((entry) => `${entry.total} ${tipoLabels[entry.rotulo] || entry.rotulo.toLowerCase()}`)
            .join(' e ')}. A distribuição por grau é de ${a.por_grau
              .map((entry) => `${entry.total} em ${entry.rotulo.toLowerCase()}`)
              .join(', ')}. As instituições estão distribuídas em ${a.estados} estados e ${a.regioes} regiões.
        </p>

        <h2>Como os dados foram organizados</h2>
        <ul>
          <li>Leitura da aba <strong>Plan1</strong> da planilha original, com 259 registros válidos.</li>
          <li>Normalização de espaços, pontuação, nomes de instituições e estados.</li>
          <li>Conversão dos códigos de grau, nível de ensino e foco temático em rótulos legíveis.</li>
          <li>Derivação da região a partir do estado e classificação da área a partir do nome do programa.</li>
          <li>Busca dos registros no Catálogo de Teses e Dissertações da CAPES e na BDTD para completar nome do autor, orientação, grau, resumo, palavras-chave e links de acesso.</li>
          <li>Geração de um índice de busca e de uma ficha completa por registro.</li>
        </ul>

        <h2>Enriquecimento e links</h2>
        <p>
          Nomes de autores e orientadores foram conferidos no Catálogo de Teses e Dissertações da
          CAPES. Resumos, palavras-chave em português e links de acesso são extraídos da página de
          cada registro na BDTD; quando o registro não está disponível na BDTD, a equipe usa o
          repositório institucional da universidade. Links do Sucupira não são usados porque
          dependem de sessão e não funcionam como endereço público estável. Registros sem
          correspondência segura mantêm os dados originais da planilha e podem ser revisados
          manualmente.
        </p>

        <div class="callout callout--info">
          <strong>Acesso aos trabalhos.</strong> Este site não hospeda os arquivos das teses e
          dissertações. Cada registro indica o link de acesso ao trabalho no site de origem; a
          disponibilidade do arquivo depende do repositório institucional ou da base que o publica.
        </div>

        <div class="callout">
          <strong>Atenção aos códigos de foco temático.</strong> A legenda original da planilha
          descreve os focos 1 a 8. Os códigos 9, 10 e 11 aparecem nos dados, mas não têm legenda;
          foram interpretados como <em>Avaliação</em>, <em>Erros e dificuldades de aprendizagem</em>
          e <em>Outros temas</em>. Essa interpretação deve ser revisada pela equipe responsável.
        </div>

        <h2>Códigos de grau</h2>
        <table>
          <thead><tr><th>Código</th><th>Rótulo</th><th>Registros</th></tr></thead>
          <tbody>
            ${a.por_grau
              .map(
                (entry) =>
                  `<tr><td>${entry.rotulo === 'Mestrado Acadêmico' ? 'MA' : entry.rotulo === 'Mestrado Profissional' ? 'MP' : 'DO'}</td><td>${entry.rotulo}</td><td>${entry.total}</td></tr>`
              )
              .join('')}
          </tbody>
        </table>

        <h2>Códigos de foco temático</h2>
        <table>
          <thead><tr><th>Código</th><th>Rótulo</th><th>Registros</th></tr></thead>
          <tbody>
            ${focosOrdenados
              .map(
                (entry) =>
                  `<tr><td>${focoCode(entry.rotulo)}</td><td>${esc(entry.rotulo)}</td><td>${entry.total}</td></tr>`
              )
              .join('')}
          </tbody>
        </table>

        <h2>Níveis de ensino</h2>
        <p>
          O campo “Nível de Ensino Pesquisado” usa códigos de 0 a 13. O código 0 foi tratado como
          <strong>não informado</strong>; os demais seguem a legenda da planilha. Registros que
          abrangem mais de uma etapa aparecem em categorias combinadas.
        </p>

        <h2>Limitações</h2>
        <ul>
          <li>O acervo reflete o recorte temporal da planilha original (1984–2013) e não é uma atualização contínua.</li>
          <li>Alguns campos estão incompletos: ${comFoco} registros têm foco temático informado; parte dos resumos, metodologias e palavras-chave está vazia.</li>
          <li>Os links para texto completo foram localizados na CAPES/BDTD quando disponíveis; nem todos os registros têm texto completo em acesso aberto.</li>
          <li>A classificação de área e a padronização de instituições são interpretações editoriais e podem ser revisadas.</li>
          <li>O site não substitui a conferência na fonte original (catálogo da instituição, BDTD ou currículo do autor).</li>
        </ul>

        <h2>Downloads</h2>
        <div class="tainacan-downloads">
          <a href="./dados/teses.csv" download><strong>CSV normalizado</strong><span>259 registros, uma linha por trabalho</span></a>
          <a href="./data/indice.json" download><strong>JSON de índice</strong><span>Campos de busca e filtros</span></a>
          <a href="./data/agregados.json" download><strong>JSON de agregados</strong><span>Séries e contagens usadas nos gráficos</span></a>
        </div>

        <h2>Como citar</h2>
        <p>Ao reutilizar os dados, cite a planilha de origem e este repositório. Uma sugestão:</p>
        <div class="callout">
          REPOSITÓRIO DE TESES E DISSERTAÇÕES EM EDUCAÇÃO ESTATÍSTICA. <em>Acervo digital
          (1984–2013)</em>. Dados organizados a partir da planilha “Estado da arte”. Disponível em:
          [endereço do site]. Acesso em: [data].
        </div>

        <h2>Sobre a publicação</h2>
        <p>
          O site é estático: os dados são gerados a partir da planilha e publicados como arquivos
          JSON, sem banco de dados ou servidor de aplicação. A interface retoma os elementos do
          tema Tainacan Interface (tipografia Roboto, paleta teal/cinza e ícones TainacanIcons).
        </p>
        <p>
          Fontes de enriquecimento:
          <a href="https://catalogodeteses.capes.gov.br/" target="_blank" rel="noopener noreferrer">Catálogo de Teses e Dissertações da CAPES</a>
          e
          <a href="https://bdtd.ibict.br/" target="_blank" rel="noopener noreferrer">BDTD</a>.
        </p>

        <section class="about-credits" aria-labelledby="creditos-title">
          <h2 id="creditos-title">Nota e créditos</h2>
          <p>
            O site foi construído a partir do levantamento de estado da arte realizado pelo
            <a href="https://orcid.org/0000-0002-9108-9826" target="_blank" rel="noopener noreferrer">Dr. Rodrigo Medeiros dos Santos</a>,
            durante seu doutorado na Universidade Estadual de Campinas (UNICAMP), sob a orientação de
            <a href="https://orcid.org/0000-0001-5536-0781" target="_blank" rel="noopener noreferrer">Dario Fiorentini</a>.
            A tese está disponível no
            <a href="https://repositorio.unicamp.br/acervo/detalhe/963478" target="_blank" rel="noopener noreferrer">repositório da UNICAMP</a>.
          </p>
          <p>
            As informações foram posteriormente validadas por meio de consulta ao Catálogo de Teses e
            Dissertações da CAPES e à Biblioteca Digital Brasileira de Teses e Dissertações (BDTD).
          </p>
          <p>
            O desenvolvimento deste site é uma iniciativa independente de
            <strong>Gerlan Silva da Silva</strong>, doutorando do Programa de Pós-Graduação em Educação
            da Universidade Federal de São Carlos (UFSCar).
          </p>

          <div class="credit-logos">
            <a href="https://bdtd.ibict.br/" target="_blank" rel="noopener noreferrer" aria-label="Biblioteca Digital Brasileira de Teses e Dissertações">
              <img class="credit-logo credit-logo--bdtd" src="./assets/images/logo-bdtd.png" alt="BDTD — Biblioteca Digital Brasileira de Teses e Dissertações" />
            </a>
            <a href="https://catalogodeteses.capes.gov.br/" target="_blank" rel="noopener noreferrer" aria-label="Catálogo de Teses e Dissertações da CAPES">
              <img class="credit-logo credit-logo--capes" src="./assets/images/logo-capes-catalogo.png" alt="CAPES" />
              <span class="credit-logo-label">Catálogo de Teses e Dissertações</span>
            </a>
          </div>
        </section>
      </div>
    </div>
  `;

  announce('Página sobre a metodologia e os dados.');
}

function focoCode(label) {
  const map = {
    'Processo de ensino e aprendizagem da Estocástica': '1',
    'Formação inicial/continuada e desenvolvimento profissional de professores': '2',
    'TICs, materiais e recursos didáticos': '3',
    'Cognição e Psicologia da Educação Estatística': '4',
    'Currículo e análise de conteúdo bibliográfico': '5',
    'Crenças, concepções, atitudes e saberes práticos': '6',
    'História, Filosofia e revisão da literatura': '7',
    'Contexto sociocultural e político do ensino-aprendizagem': '8',
    Avaliação: '9',
    'Erros e dificuldades de aprendizagem': '10',
    'Outros temas': '11',
    'Não informado': '—',
  };
  return map[label] || '—';
}

/* --- Erros --------------------------------------------------------------- */

function renderError(error) {
  console.error(error);
  const notFound = error.status === 404;
  app.innerHTML = `
    <div class="tainacan-page-wrap max-large margin-one-column">
      <div class="tainacan-empty">
        <i class="tainacan-icon tainacan-icon-alertcircle" aria-hidden="true"></i>
        <h2>${notFound ? 'Registro não encontrado' : 'Não foi possível carregar o repositório'}</h2>
        <p>${esc(error.message || String(error))}</p>
        <div class="tainacan-item-links" style="justify-content:center">
          <a href="#/acervo">Voltar ao acervo</a>
          <a href="#/">Ir para o início</a>
        </div>
      </div>
    </div>
  `;
  announce(notFound ? 'Registro não encontrado.' : 'Erro ao carregar o repositório.');
}

/* --- Filtros mobile ------------------------------------------------------ */

function openFilters() {
  document.body.classList.add('tainacan-filters-open');
  $$('[data-open-filters]').forEach((button) => button.setAttribute('aria-expanded', 'true'));
  const scrim = $('.tainacan-filters-scrim');
  if (scrim) scrim.hidden = false;
  $('.tainacan-filters [data-close-filters]')?.focus({ preventScroll: true });
}

function closeFilters(restoreFocus = true) {
  const wasOpen = document.body.classList.contains('tainacan-filters-open');
  document.body.classList.remove('tainacan-filters-open');
  $$('[data-open-filters]').forEach((button) => button.setAttribute('aria-expanded', 'false'));
  const scrim = $('.tainacan-filters-scrim');
  if (scrim) scrim.hidden = true;
  if (wasOpen && restoreFocus) $('[data-open-filters]')?.focus({ preventScroll: true });
}

function clearAll() {
  state.q = '';
  state.filters = emptyFilters();
  state.page = 1;
  syncHeaderSearch();
  replaceHash();
  renderAcervo();
  announce('Busca e filtros removidos.');
}

/* --- Eventos globais ----------------------------------------------------- */

app.addEventListener('change', (event) => {
  const checkbox = event.target.closest('input[data-filter]');
  if (checkbox) {
    const key = checkbox.dataset.filter;
    if (checkbox.checked) state.filters[key].add(checkbox.value);
    else state.filters[key].delete(checkbox.value);
    state.page = 1;
    renderResults();
    return;
  }

  const select = event.target.closest('select[data-filter-select]');
  if (select) {
    state.filters[select.dataset.filterSelect] = select.value;
    state.page = 1;
    renderResults();
    return;
  }

  if (event.target.id === 'sort-field') {
    state.sortField = event.target.value;
    state.page = 1;
    renderResults();
    return;
  }

  if (event.target.id === 'per-page') {
    state.perPage = Number(event.target.value) || 20;
    state.page = 1;
    renderResults();
    return;
  }

  if (event.target.id === 'go-to-page') {
    state.page = Number(event.target.value) || 1;
    renderResults();
  }
});

app.addEventListener('click', (event) => {
  const mode = event.target.closest('[data-mode]');
  if (mode) {
    state.mode = mode.dataset.mode;
    renderResults();
    return;
  }

  const direction = event.target.closest('[data-sort-dir]');
  if (direction) {
    state.sortDir = direction.dataset.sortDir;
    state.page = 1;
    renderResults();
    return;
  }

  const pageButton = event.target.closest('button[data-page]');
  if (pageButton && !pageButton.disabled) {
    state.page = Number(pageButton.dataset.page) || 1;
    renderResults();
    $('#results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }

  const remove = event.target.closest('[data-remove-filter]');
  if (remove) {
    const key = remove.dataset.removeFilter;
    const value = remove.dataset.value;
    if (key === 'q') {
      state.q = '';
      syncHeaderSearch();
    } else if (key === 'estado' || key === 'instituicao') {
      state.filters[key] = '';
    } else if (state.filters[key]) {
      state.filters[key].delete(value);
    }
    state.page = 1;
    renderResults();
    return;
  }

  if (event.target.closest('[data-clear-filters]')) {
    clearAll();
    return;
  }

  if (event.target.closest('[data-open-filters]')) {
    openFilters();
    return;
  }

  if (event.target.closest('[data-close-filters]')) {
    closeFilters();
  }
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    if (document.body.classList.contains('tainacan-filters-open')) closeFilters();
    if (headerSearch && !headerSearch.hidden) closeHeaderSearch();
  }
});

window.addEventListener('hashchange', route);

route();
