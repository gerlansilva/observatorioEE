const DEFAULT_REPO = 'gerlansilva/observatorioEE';
const DEFAULT_BRANCH = 'main';

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
    },
  });
}

export function requireAuth(request, env) {
  const expected = env.ADMIN_TOKEN || '';
  const header = request.headers.get('authorization') || '';
  const provided = header.startsWith('Bearer ') ? header.slice(7) : '';
  return Boolean(expected) && provided === expected;
}

export function authError() {
  return json({ error: 'Não autorizado. Informe o token administrativo.' }, 401);
}

export function validId(id) {
  return /^[a-z0-9][a-z0-9-]{0,120}$/.test(String(id || ''));
}

function encodeBase64(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function decodeBase64(value) {
  const binary = atob(value.replace(/\s/g, ''));
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new TextDecoder().decode(bytes);
}

export function repoConfig(env) {
  return {
    repo: env.GITHUB_REPO || DEFAULT_REPO,
    branch: env.GITHUB_BRANCH || DEFAULT_BRANCH,
    token: env.GITHUB_TOKEN || '',
  };
}

export async function github(env, path, options = {}) {
  const { repo, branch, token } = repoConfig(env);
  if (!token) {
    throw new Error('GITHUB_TOKEN não configurado no Cloudflare Pages.');
  }
  const url = new URL(`https://api.github.com/repos/${repo}/contents/${path}`);
  if ((options.method || 'GET') === 'GET') url.searchParams.set('ref', branch);
  const response = await fetch(url.toString(), {
    method: options.method || 'GET',
    headers: {
      authorization: `Bearer ${token}`,
      accept: 'application/vnd.github+json',
      'x-github-api-version': '2022-11-28',
      'content-type': 'application/json',
      'user-agent': 'observatorio-ee-admin',
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { message: text };
  }
  if (!response.ok && response.status !== 404) {
    throw new Error(data.message || `GitHub API retornou ${response.status}.`);
  }
  return { status: response.status, data };
}

export function itemPath(id) {
  return `site/public/data/itens/${id}.json`;
}

export function decodeContent(data) {
  return decodeBase64(data.content || '');
}

export function encodeContent(value) {
  return encodeBase64(JSON.stringify(value, null, 2) + '\n');
}

export function validateItem(item) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    return 'A ficha precisa ser um objeto JSON.';
  }
  if (!validId(item.id)) return 'ID inválido. Use letras minúsculas, números e hífens.';
  if (!String(item.titulo || '').trim()) return 'Informe o título.';
  if (!String(item.autor || '').trim()) return 'Informe a autoria.';
  if (!Number(item.ano)) return 'Informe um ano válido.';
  if (item.tags && !Array.isArray(item.tags)) return 'Palavras-chave precisam ser uma lista.';
  if (item.links && typeof item.links !== 'object') return 'Links precisam ser um objeto.';
  return '';
}

export function commitMessage(action, id) {
  return `${action} ficha ${id} pelo painel administrativo`;
}
