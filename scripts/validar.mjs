#!/usr/bin/env node
/**
 * Valida a integridade dos dados gerados antes de publicar.
 * Uso: node scripts/validar.mjs
 */

import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DATA = path.join(ROOT, 'site/public/data');
const ITEMS = path.join(DATA, 'itens');
const CSV = path.join(ROOT, 'site/public/dados/teses.csv');

const errors = [];
const warnings = [];

function check(condition, message) {
  if (!condition) errors.push(message);
}

function warn(condition, message) {
  if (!condition) warnings.push(message);
}

async function readJSON(file) {
  try {
    return JSON.parse(await readFile(file, 'utf8'));
  } catch (error) {
    errors.push(`JSON inválido em ${path.relative(ROOT, file)}: ${error.message}`);
    return null;
  }
}

async function main() {
  const index = await readJSON(path.join(DATA, 'indice.json'));
  const agregados = await readJSON(path.join(DATA, 'agregados.json'));
  if (!index || !agregados) {
    report();
    return;
  }

  check(Array.isArray(index), 'indice.json deve ser uma lista.');
  check(index.length === agregados.total, `Índice (${index.length}) difere do total (${agregados.total}).`);
  check(agregados.periodo.inicio === 1984, 'Ano inicial deveria ser 1984.');
  check(agregados.periodo.fim === 2013, 'Ano final deveria ser 2013.');

  const ids = new Set();
  const required = ['id', 'titulo', 'autor', 'ano', 'tipo', 'grau', 'instituicao', 'area', 'foco', 'conteudo', 'busca_norm'];

  for (const entry of index) {
    for (const field of required) {
      check(entry[field] !== undefined && entry[field] !== '', `Registro ${entry.id || '?'} sem o campo ${field}.`);
    }
    check(!ids.has(entry.id), `ID duplicado: ${entry.id}`);
    ids.add(entry.id);

    const itemFile = path.join(ITEMS, `${entry.id}.json`);
    const item = await readJSON(itemFile);
    if (!item) continue;
    check(item.id === entry.id, `Ficha ${entry.id}: id interno diferente.`);
    check(item.titulo === entry.titulo, `Ficha ${entry.id}: título diferente do índice.`);
    check(Boolean(item.links?.google_scholar), `Ficha ${entry.id}: link do Google Scholar ausente.`);
    check(Boolean(item.links?.bdtd), `Ficha ${entry.id}: link da BDTD ausente.`);
  }

  const files = (await readdir(ITEMS, { withFileTypes: true }))
    .filter((entry) => entry.isFile() && entry.name.endsWith('.json'))
    .map((entry) => entry.name.replace(/\.json$/, ''));
  check(files.length === index.length, `Pasta de fichas tem ${files.length} arquivos; índice tem ${index.length}.`);
  const fileSet = new Set(files);
  for (const id of ids) check(fileSet.has(id), `Ficha ausente: ${id}.json`);
  for (const id of fileSet) check(ids.has(id), `Ficha órfã: ${id}.json`);

  const sum = (series) => series.reduce((total, entry) => total + Number(entry.total || 0), 0);
  check(sum(agregados.por_ano) === agregados.total, 'Soma de por_ano difere do total.');
  check(sum(agregados.por_grau) === agregados.total, 'Soma de por_grau difere do total.');
  check(sum(agregados.por_tipo) === agregados.total, 'Soma de por_tipo difere do total.');
  check(sum(agregados.por_regiao) === agregados.total, 'Soma de por_regiao difere do total.');
  check(agregados.por_ano.length === 30, 'por_ano deveria ter 30 anos (1984–2013).');

  try {
    const csv = await readFile(CSV, 'utf8');
    check(csv.startsWith('\uFEFF'), 'O CSV público deveria começar com BOM (UTF-8).');
    check(csv.includes('titulo'), 'O CSV público não tem a coluna titulo.');
    check(csv.split('\n').length > 200, 'O CSV público parece incompleto.');
  } catch {
    errors.push(`CSV público não encontrado em ${path.relative(ROOT, CSV)}.`);
  }

  warn(agregados.atualizado_em, 'agregados.atualizado_em ausente.');
  report();
}

function report() {
  if (warnings.length) {
    console.warn('\nAvisos:');
    for (const message of warnings) console.warn(`  ! ${message}`);
  }
  if (errors.length) {
    console.error(`\n✗ ${errors.length} problema(s) encontrado(s):`);
    for (const message of errors) console.error(`  - ${message}`);
    process.exitCode = 1;
    return;
  }
  console.log('✓ Dados válidos.');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
