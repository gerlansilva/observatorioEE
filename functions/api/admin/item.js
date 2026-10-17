import {
  authError,
  commitMessage,
  decodeContent,
  encodeContent,
  github,
  itemPath,
  json,
  requireAuth,
  validId,
  validateItem,
} from './_utils.js';

export async function onRequest({ request, env }) {
  if (!requireAuth(request, env)) return authError();

  const url = new URL(request.url);
  const id = url.searchParams.get('id') || '';
  if (!validId(id)) return json({ error: 'ID inválido.' }, 400);

  try {
    if (request.method === 'GET') {
      const result = await github(env, itemPath(id));
      if (result.status === 404) return json({ error: 'Ficha não encontrada.' }, 404);
      return json(JSON.parse(decodeContent(result.data)));
    }

    if (request.method === 'PUT') {
      const item = await request.json();
      item.id = id;
      const error = validateItem(item);
      if (error) return json({ error }, 400);
      const body = JSON.stringify(item);
      if (body.length > 250_000) return json({ error: 'Ficha muito grande.' }, 413);

      const existing = await github(env, itemPath(id));
      const payload = {
        message: commitMessage(existing.status === 404 ? 'Cria' : 'Atualiza', id),
        content: encodeContent(item),
        branch: env.GITHUB_BRANCH || 'main',
      };
      if (existing.status !== 404) payload.sha = existing.data.sha;

      const result = await github(env, itemPath(id), { method: 'PUT', body: payload });
      return json({ ok: true, commit: result.data.commit?.html_url || '' });
    }

    if (request.method === 'DELETE') {
      const existing = await github(env, itemPath(id));
      if (existing.status === 404) return json({ error: 'Ficha não encontrada.' }, 404);
      const result = await github(env, itemPath(id), {
        method: 'DELETE',
        body: {
          message: commitMessage('Exclui', id),
          sha: existing.data.sha,
          branch: env.GITHUB_BRANCH || 'main',
        },
      });
      return json({ ok: true, commit: result.data.commit?.html_url || '' });
    }

    return json({ error: 'Método não permitido.' }, 405);
  } catch (error) {
    return json({ error: error.message || 'Erro ao acessar o GitHub.' }, 502);
  }
}
