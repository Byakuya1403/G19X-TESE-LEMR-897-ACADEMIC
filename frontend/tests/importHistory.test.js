import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let server;
let View;
before(async () => {
  server = await createServer({
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  View = (await server.ssrLoadModule('/src/components/ImportHistory.jsx')).ImportHistoryView;
});
after(async () => {
  await server?.close();
});
const batch = {
  id: 12,
  filename: 'presupuesto.csv',
  currency: 'MXN',
  username: 'analista',
  entry_count: 36,
  period_from: '2026-01',
  period_to: '2026-12',
};
function render(overrides = {}) {
  return renderToStaticMarkup(
    React.createElement(View, {
      page: { items: [batch], total: 1, limit: 25, offset: 0 },
      loading: false,
      error: '',
      busy: false,
      selected: batch,
      confirmation: '',
      deleteError: '',
      ...overrides,
    }),
  );
}
function deleteButton(html) {
  return html.match(/<button[^>]*>Eliminar definitivamente<\/button>/)?.[0];
}

test('deletion requires the exact code for the selected import', () => {
  for (const code of ['', 'ELIMINAR', 'eliminar 12', 'ELIMINAR 13']) {
    assert.ok(deleteButton(render({ confirmation: code })).includes('disabled'));
  }
  assert.ok(!deleteButton(render({ confirmation: 'ELIMINAR 12' })).includes('disabled'));
  const html = render();
  for (const text of [
    'presupuesto.csv',
    '36 partidas',
    'enero de 2026',
    'diciembre de 2026',
    'Cancelar',
    'ELIMINAR 12',
    'espacio financiero compartido',
  ])
    assert.ok(html.includes(text), text);
});

test('busy state prevents repeated deletion or cancellation', () => {
  const html = render({ busy: true, confirmation: 'ELIMINAR 12' });
  assert.match(html, /<button[^>]*disabled[^>]*>Eliminando…<\/button>/);
  assert.match(html, /<button[^>]*disabled[^>]*>Cancelar<\/button>/);
});

test('errors preserve confirmation context and empty history is explicit', () => {
  const html = render({ deleteError: 'La importación ya no existe.' });
  assert.ok(html.includes('role="alert"') && html.includes('La importación ya no existe.'));
  assert.ok(html.includes('ELIMINAR 12'));
  const empty = render({ page: { items: [], total: 0, limit: 25, offset: 0 }, selected: null });
  assert.ok(empty.includes('No hay importaciones guardadas'));
  assert.ok(deleteButton(empty).includes('disabled'));
});

test('pagination exposes distinct loads even when names match', () => {
  const html = render({
    page: { items: [batch, { ...batch, id: 13 }], total: 30, limit: 25, offset: 0 },
    selected: null,
  });
  assert.ok(html.includes('Eliminar carga 12: presupuesto.csv'));
  assert.ok(html.includes('Eliminar carga 13: presupuesto.csv'));
  assert.ok(html.includes('30 cargas'));
  assert.match(html, /<button[^>]*disabled[^>]*>Anterior<\/button>/);
  assert.ok(!html.match(/<button[^>]*>Siguiente<\/button>/)[0].includes('disabled'));
});
