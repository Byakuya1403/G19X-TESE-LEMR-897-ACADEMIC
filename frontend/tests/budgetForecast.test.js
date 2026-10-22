import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

let server;
let View;
let Dashboard;
let Summary;
before(async () => {
  server = await createServer({
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  View = (await server.ssrLoadModule('/src/components/BudgetForecast.jsx')).BudgetForecastView;
  Summary = (await server.ssrLoadModule('/src/components/BudgetForecast.jsx'))
    .BudgetForecastSummary;
  Dashboard = (await server.ssrLoadModule('/src/components/Dashboard.jsx')).default;
});
after(async () => {
  await server?.close();
});

// Test-only values. The actual component obtains every amount from the API.
function result(overrides = {}) {
  return {
    disponible: true,
    moneda: 'MXN',
    periodo_base: '2026-06',
    periodo_pronosticado: '2026-07',
    presupuesto_actual: 1500,
    presupuesto_estimado: 1600,
    variacion_porcentual: 6.67,
    meses_analizados: 6,
    registros_analizados: 6,
    importaciones_analizadas: 6,
    advertencias: [],
    evaluacion: { mae: 0, mae_referencia: 100, meses_validacion: 3 },
    historial: Array.from({ length: 6 }, (_, i) => ({
      periodo: `2026-0${i + 1}`,
      presupuesto: 1000 + i * 100,
      ejecucion_completada: true,
    })),
    ...overrides,
  };
}
function render(props = {}) {
  return renderToStaticMarkup(
    React.createElement(View, {
      result: result(),
      financial: true,
      loading: false,
      error: '',
      ...props,
    }),
  );
}

test('renders amounts, variation, model, MAE and separate estimated chart point', () => {
  const html = render();
  assert.ok(html.includes('Predicción inteligente de presupuesto'));
  assert.ok(html.includes('$1,600.00'));
  assert.ok(html.includes('+6.67 %'));
  assert.ok(html.includes('julio de 2026'));
  assert.ok(html.includes('Error histórico (MAE)'));
  assert.ok(html.includes('trend-projected') && html.includes('trend-diamond'));
  assert.ok(html.includes('<caption>') && html.includes('Ver los valores de la gráfica'));
  const table = html.slice(html.indexOf('<tbody>'));
  assert.ok(table.indexOf('enero de 2026') < table.indexOf('junio de 2026'));
  assert.ok(table.indexOf('junio de 2026') < table.indexOf('julio de 2026'));
});

test('insufficient history shows no invented forecast or projected chart segment', () => {
  const html = render({
    result: result({
      disponible: false,
      presupuesto_estimado: null,
      mensaje: 'Histórico insuficiente.',
    }),
  });
  assert.ok(html.includes('Predicción no disponible.'));
  assert.ok(html.includes('Histórico insuficiente.'));
  assert.ok(!html.includes('trend-projected') && !html.includes('trend-diamond'));
  assert.ok(!html.includes('Variación respecto al presupuesto anterior'));
});

test('uses cumulative database history without any CSV selector', () => {
  const html = render();
  assert.ok(html.includes('histórico guardado en la base de datos'));
  assert.ok(html.includes('6 importaciones'));
  assert.ok(!html.includes('<select') && !html.includes('Archivo analizado'));
});

test('original summary card uses the same ML result and never the old spending average', () => {
  const html = renderToStaticMarkup(
    React.createElement(Summary, {
      result: result(),
      financial: true,
      loading: false,
      error: '',
    }),
  );
  assert.ok(html.includes('$1,600.00'));
  assert.ok(html.includes('julio de 2026'));
  assert.ok(html.includes('+6.67 %'));
  assert.ok(html.includes('Fuente: base de datos'));
  assert.ok(!html.includes('Gasto proyectado de referencia'));
  for (const props of [
    { financial: false },
    { loading: true },
    { error: 'Error' },
    { result: result({ disponible: false, mensaje: 'Histórico insuficiente' }) },
  ]) {
    const unavailable = renderToStaticMarkup(
      React.createElement(Summary, {
        result: result(),
        financial: true,
        loading: false,
        error: '',
        ...props,
      }),
    );
    assert.ok(!unavailable.includes('$1,600.00'));
  }
});

test('guest, loading and network errors do not display stale estimates', () => {
  for (const props of [{ financial: false }, { loading: true }, { error: 'Error de conexión' }]) {
    const html = render(props);
    assert.ok(!html.includes('$1,600.00') && !html.includes('trend-projected'));
  }
  assert.ok(render({ error: 'Error de conexión' }).includes('role="alert"'));
});

test('zero baseline never displays NaN or Infinity as a variation', () => {
  const html = render({ result: result({ presupuesto_actual: 0, variacion_porcentual: null }) });
  assert.ok(html.includes('No calculable con base cero'));
  assert.ok(!html.includes('NaN') && !html.includes('Infinity'));
});

test('dashboard preserves panels and connects the original card to the budget forecast', () => {
  const html = renderToStaticMarkup(
    React.createElement(Dashboard, {
      entries: [],
      currency: 'MXN',
      category: '',
      period: '2026-01',
      user: null,
      onPeriodChange: () => {},
      onImport: () => {},
      data: {
        income: { budget: 0, actual: null, pending: 0 },
        expense: { budget: 0, actual: null, pending: 0 },
        balance: null,
        alerts: [],
      },
    }),
  );
  for (const label of [
    'Presupuestos mensuales',
    'PREDICCIÓN DEL SIGUIENTE MES',
    'Ingresos presupuestados',
    'Egresos reales',
    'Centro de alertas',
    'Predicción inteligente de presupuesto',
  ]) {
    assert.ok(html.includes(label), label);
  }
  assert.ok(!html.includes('999,999') && !html.includes('Gasto proyectado de referencia'));
  assert.ok(
    html.indexOf('Centro de alertas') < html.indexOf('Predicción inteligente de presupuesto'),
  );
});

test('pending execution shows registered budget history and an available prediction', () => {
  const pending = result({
    historial: result().historial.map((point) => ({ ...point, ejecucion_completada: false })),
    advertencias: [
      'Hay gastos reales pendientes; se utilizan los presupuestos asignados ya registrados.',
    ],
  });
  const html = render({ result: pending });
  assert.ok(html.includes('$1,600.00'));
  assert.ok(html.includes('trend-projected'));
  assert.ok(html.includes('Presupuesto registrado · ejecución pendiente'));
  assert.ok(!html.includes('Predicción no disponible') && !html.includes('trend-pending'));
});

test('changing budget composition is shown as a warning without hiding a valid estimate', () => {
  const html = render({
    result: result({
      composicion_variable: true,
      advertencias: ['La composición de las partidas cambia entre meses.'],
    }),
  });
  assert.ok(html.includes('$1,600.00') && html.includes('trend-projected'));
  assert.ok(html.includes('La composición de las partidas cambia entre meses.'));
});
