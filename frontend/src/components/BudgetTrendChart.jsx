import React from 'react';
import { formatMoney, monthLabel } from '../utils/formatters';

export default function BudgetTrendChart({ result }) {
  const history = result.historial;
  if (!history.length) return null;

  const points = history.map((point) => ({
    period: point.periodo,
    amount: point.presupuesto,
    estimated: false,
    executionComplete: point.ejecucion_completada,
  }));
  if (result.disponible) {
    points.push({
      period: result.periodo_pronosticado,
      amount: result.presupuesto_estimado,
      estimated: true,
    });
  }
  const maximum = Math.max(1, ...points.map((point) => point.amount)) * 1.15;
  const x = (index) => 95 + (index * 600) / Math.max(1, points.length - 1);
  const y = (amount) => 220 - (amount * 180) / maximum;
  const path = history
    .map((point, index) => `${index ? 'L' : 'M'} ${x(index)} ${y(point.presupuesto)}`)
    .join(' ');
  const ticks = [
    ...new Set(
      Array.from({ length: Math.min(5, points.length) }, (_, i) =>
        Math.round((i * (points.length - 1)) / Math.max(1, Math.min(5, points.length) - 1)),
      ),
    ),
  ];
  const compact = (value) =>
    new Intl.NumberFormat('es-MX', {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);

  return (
    <div className="budget-trend">
      <h3>Tendencia del presupuesto de egresos</h3>
      <div className="trend-legend">
        <span>● Histórico registrado</span>
        {result.disponible && <span className="trend-estimate">◆ Estimación del modelo</span>}
      </div>
      <div className="trend-scroll">
        <svg
          viewBox="0 0 760 275"
          role="img"
          aria-label={`Presupuestos mensuales en ${result.moneda}, ordenados por fecha. Los valores exactos están en la tabla de datos.`}
        >
          <text x="18" y="22" className="trend-axis">
            {result.moneda}
          </text>
          {[0, 1, 2, 3].map((tick) => {
            const value = (maximum * tick) / 3;
            return (
              <g key={tick}>
                <line x1="95" x2="695" y1={y(value)} y2={y(value)} className="trend-grid" />
                <text x="84" y={y(value) + 4} textAnchor="end" className="trend-axis">
                  {compact(value)}
                </text>
              </g>
            );
          })}
          <path d={path} className="trend-history" />
          {result.disponible && (
            <line
              x1={x(history.length - 1)}
              y1={y(history.at(-1).presupuesto)}
              x2={x(history.length)}
              y2={y(result.presupuesto_estimado)}
              className="trend-projected"
            />
          )}
          {points.map((point, index) => (
            <g key={point.period}>
              {point.estimated ? (
                <path
                  d={`M ${x(index)} ${y(point.amount) - 7} l 7 7 l -7 7 l -7 -7 Z`}
                  className="trend-diamond"
                >
                  <title>{`${monthLabel(point.period)}: ${formatMoney(point.amount, result.moneda)} estimados`}</title>
                </path>
              ) : (
                <circle cx={x(index)} cy={y(point.amount)} r="4" className="trend-point">
                  <title>{`${monthLabel(point.period)}: ${formatMoney(point.amount, result.moneda)} registrados${point.executionComplete ? '' : ' · ejecución pendiente; presupuesto conocido'}`}</title>
                </circle>
              )}
            </g>
          ))}
          {ticks.map((index) => (
            <text
              key={index}
              x={x(index)}
              y="249"
              textAnchor={index === 0 ? 'start' : index === points.length - 1 ? 'end' : 'middle'}
              className="trend-axis"
            >
              {points[index].period}
              {points[index].estimated ? ' · estimado' : ''}
            </text>
          ))}
        </svg>
      </div>
      <details>
        <summary>Ver los valores de la gráfica</summary>
        <div className="tablewrap">
          <table>
            <caption>Presupuestos de egresos · {result.moneda}</caption>
            <thead>
              <tr>
                <th>Periodo</th>
                <th>Presupuesto</th>
                <th>Tipo</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.period}>
                  <td>{monthLabel(point.period)}</td>
                  <td>{formatMoney(point.amount, result.moneda)}</td>
                  <td>
                    {point.estimated
                      ? 'Estimado'
                      : point.executionComplete
                        ? 'Histórico registrado'
                        : 'Presupuesto registrado · ejecución pendiente'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
