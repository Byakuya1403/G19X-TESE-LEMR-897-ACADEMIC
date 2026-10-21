import React from 'react';
import { budgetHistory } from '../budgetHistory';
import { formatMoney, monthLabel } from '../utils/formatters';
import { BudgetForecastSummary, BudgetForecastView, useBudgetForecast } from './BudgetForecast';

export default function Dashboard({
  data,
  entries,
  currency,
  category,
  period,
  user,
  onPeriodChange,
  onImport,
}) {
  const history = budgetHistory(entries, currency, category, period);
  const forecast = useBudgetForecast({ currency, category, period, user, entries });
  function money(value) {
    return formatMoney(value, currency);
  }
  return (
    <>
      <div className="topgrid dashboard-main">
        <article className="panel historypanel">
          <div className="paneltitle">
            <h2>Presupuestos mensuales</h2>
            <span>{history.length} periodos</span>
          </div>
          <p className="muted">
            Ingresos y egresos del mes seleccionado. Cambia el periodo en el filtro superior para
            consultar otro mes.
          </p>
          <div className="historylist">
            {history.length ? (
              history.map((month) => (
                <section
                  className={'historymonth ' + (month.period === period ? 'selectedmonth' : '')}
                  key={month.period}
                >
                  <button
                    className="monthbutton"
                    onClick={() => onPeriodChange(month.period)}
                    aria-pressed={month.period === period}
                  >
                    {monthLabel(month.period)}
                    <span>{month.period === period ? 'Seleccionado' : 'Ver periodo →'}</span>
                  </button>
                  {month.categories.map((row) => (
                    <div
                      className={'budget ' + (row.nature === 'income' ? 'income-budget' : '')}
                      key={`${row.nature}:${row.category}`}
                    >
                      <div>
                        <b>
                          {row.category}{' '}
                          <small>{row.nature === 'income' ? '· Ingreso' : '· Egreso'}</small>
                        </b>
                        <strong
                          className={
                            row.nature === 'expense' && row.utilization > 100 ? 'danger' : ''
                          }
                        >
                          {row.pending
                            ? 'Pendiente'
                            : row.utilization === null
                              ? 'Sin base'
                              : row.utilization.toFixed(1) + '%'}
                        </strong>
                      </div>
                      {row.utilization === null ? (
                        <div
                          className="pendingbar"
                          aria-label={row.pending ? 'Resultado pendiente' : 'Porcentaje sin base'}
                        />
                      ) : (
                        <progress
                          value={Math.min(row.utilization, 100)}
                          max="100"
                          aria-label={`${row.category}, ${monthLabel(month.period)}: ${row.utilization.toFixed(1)}% de ${row.nature === 'income' ? 'cumplimiento' : 'ejecución'}`}
                        />
                      )}
                      <div className="muted">
                        <span>
                          {row.pending
                            ? `${money(row.known)} conocidos · ${row.pending} pendientes`
                            : `${money(row.actual)} ${row.nature === 'income' ? 'recibidos' : 'utilizados'}`}
                        </span>
                        <span>de {money(row.budget)}</span>
                      </div>
                    </div>
                  ))}
                </section>
              ))
            ) : (
              <div className="empty">
                <h3>Sin partidas para esta selección</h3>
                <p>
                  No hay partidas para el mes, categoría y moneda elegidos. Cambia los filtros o
                  importa un archivo.
                </p>
                {user?.role === 'analyst' && (
                  <button onClick={() => onImport()}>Cargar histórico →</button>
                )}
              </div>
            )}
          </div>
        </article>
        <BudgetForecastSummary {...forecast} />
      </div>
      <div className="kpis">
        {[
          ['Ingresos presupuestados', data.income.budget],
          ['Ingresos reales', data.income.actual],
          ['Egresos presupuestados', data.expense.budget],
          ['Egresos reales', data.expense.actual],
        ].map(([k, v]) => (
          <article className="panel" key={k}>
            <p>{k}</p>
            <h2>{money(v)}</h2>
            <small>
              {currency} · {monthLabel(period)}
            </small>
          </article>
        ))}
      </div>
      <article className="panel">
        <div className="paneltitle">
          <h2>Centro de alertas</h2>
          <span>{monthLabel(period)}</span>
        </div>
        <p className="muted">
          Resultado del periodo: <b>{money(data.balance)}</b> ·{' '}
          {data.income.pending + data.expense.pending} partidas pendientes.
        </p>
        {data.alerts.length ? (
          data.alerts.map((a, i) => (
            <div className="alert warning" key={i}>
              <b>{a.department}</b>
              <span>{a.message}</span>
              <strong>{money(a.deviation)}</strong>
            </div>
          ))
        ) : (
          <p className="muted">Sin desviaciones desfavorables en las partidas completadas.</p>
        )}
      </article>
      <BudgetForecastView {...forecast} />
    </>
  );
}
