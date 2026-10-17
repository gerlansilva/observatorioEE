import { authError, json, requireAuth } from './_utils.js';

export function onRequestGet({ request, env }) {
  if (!requireAuth(request, env)) return authError();
  return json({ ok: true });
}
