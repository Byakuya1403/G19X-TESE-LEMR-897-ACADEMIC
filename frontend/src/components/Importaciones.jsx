import React from 'react';
import ImportHistory from './ImportHistory';

export default function Importaciones({
  currency,
  setCurrency,
  file,
  setFile,
  repair,
  setRepair,
  preview,
  setPreview,
  busy,
  setError,
  onInspect,
  onUpload,
  revision,
  onDeleted,
  onBusyChange,
}) {
  return (
    <>
      <article className="panel">
        <h2>Importar presupuesto por partidas</h2>
        <p className="muted">
          CSV UTF-8 de hasta 2 MB y 10 000 filas. Confirma la moneda del archivo; los ingresos y
          egresos se almacenan separados.
        </p>
        <label>
          Moneda del archivo
          <select
            value={currency}
            onChange={(e) => {
              setCurrency(e.target.value);
              setPreview(null);
            }}
          >
            {['MXN', 'USD', 'EUR'].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="filelabel">
          Selecciona un CSV
          <input
            type="file"
            accept=".csv"
            disabled={busy}
            onChange={(e) => {
              setFile(e.target.files[0] || null);
              setPreview(null);
              setError('');
            }}
          />
        </label>
        <label className="checklabel">
          <input
            type="checkbox"
            checked={repair}
            onChange={(e) => {
              setRepair(e.target.checked);
              setPreview(null);
            }}
          />
          Confirmo reparar filas cuyo mes esté en Concepto y las cuatro columnas de texto estén
          desplazadas.
        </label>
        <button disabled={busy || !file} onClick={onInspect}>
          Validar y previsualizar
        </button>
        {preview && (
          <div className="note">
            <b>
              {preview.count} partidas válidas · {preview.pending} pendientes
            </b>
            {preview.warnings.map((w) => (
              <p key={w}>{w}</p>
            ))}
            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Periodo</th>
                    <th>Categoría</th>
                    <th>Concepto</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.sample.map((x) => (
                    <tr key={x.source_id}>
                      <td>{x.source_id}</td>
                      <td>{x.period}</td>
                      <td>{x.category}</td>
                      <td>{x.concept}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button disabled={busy} onClick={onUpload}>
              Confirmar importación en {currency}
            </button>
          </div>
        )}
        <p className="note">
          Columnas: ID_Registro, Anio, Mes, Categoria, Subcategoria, Concepto, Presupuesto_Estimado,
          Gasto_Real, Diferencia_Varianza, Porcentaje_Ejecucion y Estado.
          <br />
          La categoría «Ingresos» se interpreta como ingreso; las demás categorías, como egreso.
          Confirma que esa regla corresponda a tu archivo.
          <br />
          Pendiente con Gasto_Real=0 se guarda como resultado desconocido. No se aceptan negativos
          ni ajustes contables en este formato. Se conserva la fila original.
        </p>
      </article>
      <ImportHistory
        revision={revision}
        onDeleted={onDeleted}
        busy={busy}
        onBusyChange={onBusyChange}
      />
    </>
  );
}
