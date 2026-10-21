import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { formatMoney, monthLabel } from '../utils/formatters';
import BudgetTrendChart from './BudgetTrendChart';

export function BudgetForecastView({ result, loading, error, batchId, onBatchChange, financial }) {
  return (
    <article className="panel budget-forecast" aria-labelledby="budget-forecast-title">
      <div className="paneltitle">
        <h2 id="budget-forecast-title">Predicción inteligente de presupuesto</h2>
        <span>Regresión lineal</span>
      </div>
      <p className="muted">
        Presupuesto asignado a egresos, separado del gasto real. Se estima el mes siguiente al
        periodo seleccionado, usando únicamente su histórico anterior o igual a ese periodo.
      </p>
      {!financial ? (
        <p className="notice">
          Inicia sesión con un rol financiero para consultar la predicción con datos reales.
        </p>
      ) : (
        <>
          {result?.conjuntos_disponibles.length > 1 && (
            <label className="forecast-dataset">
              Archivo para esta predicción
              <select value={batchId} onChange={(event) => onBatchChange(event.target.value)}>
                <option value="">Selecciona una importación</option>
                {result.conjuntos_disponibles.map((batch) => (
                  <option key={batch.id} value={batch.id}>
                    {batch.nombre} · #{batch.id}
                  </option>
                ))}
              </select>
              <small>Solo afecta esta sección. Los archivos no se suman entre sí.</small>
            </label>
          )}
          {loading && <p role="status">Analizando el histórico de presupuestos…</p>}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {result && !loading && !error && (
            <>
              {result.batch_id && (
                <p className="muted">
                  Archivo analizado:{' '}
                  {
                    result.conjuntos_disponibles.find((batch) => batch.id === result.batch_id)
                      ?.nombre
                  }{' '}
                  · #{result.batch_id}
                </p>
              )}
              {!result.disponible ? (
                <p className="notice" role="status">
                  Predicción no disponible. {result.mensaje}
                </p>
              ) : (
                <>
                  <div className="budget-forecast-metrics">
                    <div className="budget-estimate">
                      <p>Presupuesto estimado del siguiente mes</p>
                      <h3>{formatMoney(result.presupuesto_estimado, result.moneda)}</h3>
                      <small>{result.moneda} · Presupuesto de egresos</small>
                    </div>
                    <dl>
                      <div>
                        <dt>Variación respecto al presupuesto anterior</dt>
                        <dd>
                          {result.variacion_porcentual === null
                            ? 'No calculable con base cero'
                            : `${result.variacion_porcentual > 0 ? '+' : ''}${result.variacion_porcentual.toLocaleString('es-MX', { maximumFractionDigits: 2 })} %`}
                        </dd>
                      </div>
                      <div>
                        <dt>Periodo pronosticado</dt>
                        <dd>{monthLabel(result.periodo_pronosticado)}</dd>
                      </div>
                      <div>
                        <dt>Presupuesto del mes base · {monthLabel(result.periodo_base)}</dt>
                        <dd>{formatMoney(result.presupuesto_actual, result.moneda)}</dd>
                      </div>
                      <div>
                        <dt>Modelo utilizado</dt>
                        <dd>Regresión lineal · {result.meses_analizados} meses</dd>
                      </div>
                    </dl>
                  </div>
                </>
              )}
              {result.evaluacion && (
                <p className="note">
                  Error histórico (MAE): <b>{formatMoney(result.evaluacion.mae, result.moneda)}</b>.
                  Referencia de repetir el mes anterior:{' '}
                  {formatMoney(result.evaluacion.mae_referencia, result.moneda)}. Evaluación
                  temporal en {result.evaluacion.meses_validacion} meses, siempre entrenando con
                  meses anteriores; no es un porcentaje de confianza.
                </p>
              )}
              {result.advertencias.map((warning) => (
                <p className="muted" key={warning}>
                  {warning}
                </p>
              ))}
              <BudgetTrendChart result={result} />
            </>
          )}
        </>
      )}
    </article>
  );
}

export default function BudgetForecast({
  currency,
  category,
  period,
  user,
  entries,
  request = api,
}) {
  const [batchId, setBatchId] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const financial = user?.role === 'director' || user?.role === 'analyst';

  useEffect(() => {
    if (!financial) return;
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError('');
    const query = new URLSearchParams({ currency, period });
    if (category) query.set('category', category);
    if (batchId) query.set('batch_id', batchId);
    request('/forecast/budget?' + query, { signal: controller.signal })
      .then((value) => {
        if (active) setResult(value);
      })
      .catch((reason) => {
        if (active) {
          setError(reason.message);
          setResult(null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [currency, category, period, batchId, financial, entries, request]);

  return (
    <BudgetForecastView
      result={result}
      loading={loading}
      error={error}
      batchId={batchId}
      onBatchChange={(value) => {
        setBatchId(value);
        setLoading(true);
      }}
      financial={financial}
    />
  );
}
