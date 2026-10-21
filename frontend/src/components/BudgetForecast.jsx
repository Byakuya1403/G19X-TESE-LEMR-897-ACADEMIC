import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { formatMoney, monthLabel } from '../utils/formatters';
import BudgetTrendChart from './BudgetTrendChart';

export function BudgetForecastView({ result, loading, error, financial }) {
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
          {loading && <p role="status">Analizando el histórico de presupuestos…</p>}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {result && !loading && !error && (
            <>
              <p className="muted">
                Fuente: histórico guardado en la base de datos · {result.registros_analizados}{' '}
                partidas de {result.importaciones_analizadas} importaciones.
              </p>
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

export function useBudgetForecast({ currency, category, period, user, entries, request = api }) {
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
  }, [currency, category, period, financial, entries, request]);

  return { result, loading, error, financial };
}

export function BudgetForecastSummary({ result, loading, error, financial }) {
  const ready = financial && !loading && !error && result?.disponible;
  return (
    <article className="forecast" aria-label="Predicción mensual de presupuesto">
      <p className="eyebrow">PREDICCIÓN DEL SIGUIENTE MES</p>
      <h3>
        {financial && !loading && !error && result?.periodo_pronosticado
          ? monthLabel(result.periodo_pronosticado)
          : 'Presupuesto de egresos'}
      </h3>
      <h2>
        {ready
          ? formatMoney(result.presupuesto_estimado, result.moneda)
          : 'Predicción no disponible'}
      </h2>
      <p>
        {ready ? `Presupuesto estimado · ${result.moneda}` : 'Estimación mediante regresión lineal'}
      </p>
      {ready && (
        <p>
          Variación respecto al mes base:{' '}
          {result.variacion_porcentual === null
            ? 'No calculable con base cero'
            : `${result.variacion_porcentual > 0 ? '+' : ''}${result.variacion_porcentual.toLocaleString('es-MX', { maximumFractionDigits: 2 })} %`}
        </p>
      )}
      <div className="forecastnote" role="status">
        {!financial
          ? 'Inicia sesión con un rol financiero para consultar el histórico real.'
          : loading
            ? 'Analizando los presupuestos guardados…'
            : error
              ? error
              : ready
                ? `Regresión lineal · ${result.meses_analizados} meses analizados. Fuente: base de datos. Consulta la evaluación y la tendencia debajo.`
                : result?.mensaje || 'Esperando el histórico almacenado.'}
      </div>
    </article>
  );
}
