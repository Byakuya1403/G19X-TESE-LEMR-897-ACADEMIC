import React, { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { monthLabel } from '../utils/formatters';

function periods(batch) {
  return batch.period_from
    ? `${monthLabel(batch.period_from)} — ${monthLabel(batch.period_to)}`
    : 'Sin partidas';
}

export function ImportHistoryView({
  page,
  loading,
  error,
  busy,
  selected,
  confirmation,
  deleteError,
  onSelect,
  onConfirmation,
  onCancel,
  onDelete,
  onPage,
  onReload,
  dialogRef,
}) {
  const code = selected ? `ELIMINAR ${selected.id}` : '';
  return (
    <article className="panel import-history">
      <div className="paneltitle">
        <h2>Importaciones guardadas</h2>
        <button className="secondary" disabled={busy || loading} onClick={onReload}>
          Actualizar listado
        </button>
      </div>
      <p className="muted">
        Cargas del espacio financiero compartido. Eliminar una carga retira todas sus partidas de la
        base de datos, del resumen y del histórico del forecast. No se puede deshacer desde la
        plataforma.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p role="status">Cargando importaciones…</p>
      ) : (
        <>
          {!page.items.length ? (
            <p className="muted">No hay importaciones guardadas en esta página.</p>
          ) : (
            <div className="tablewrap">
              <table>
                <caption>Archivos importados · {page.total} cargas</caption>
                <thead>
                  <tr>
                    <th>Carga / archivo</th>
                    <th>Moneda</th>
                    <th>Periodos</th>
                    <th>Partidas</th>
                    <th>Importado por</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((batch) => (
                    <tr key={batch.id}>
                      <td>
                        #{batch.id} · {batch.filename}
                      </td>
                      <td>{batch.currency}</td>
                      <td>{periods(batch)}</td>
                      <td>{batch.entry_count}</td>
                      <td>{batch.username}</td>
                      <td>
                        <button
                          className="delete-button"
                          disabled={busy}
                          onClick={() => onSelect(batch)}
                          aria-label={`Eliminar carga ${batch.id}: ${batch.filename}`}
                        >
                          Eliminar carga
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="scenario-actions">
            <button
              className="secondary"
              disabled={busy || page.offset === 0}
              onClick={() => onPage(Math.max(0, page.offset - page.limit))}
            >
              Anterior
            </button>
            <span className="muted">
              Página {Math.floor(page.offset / page.limit) + 1} · {page.total} cargas
            </span>
            <button
              className="secondary"
              disabled={busy || page.offset + page.limit >= page.total}
              onClick={() => onPage(page.offset + page.limit)}
            >
              Siguiente
            </button>
          </div>
        </>
      )}
      <dialog
        ref={dialogRef}
        className="delete-dialog"
        aria-labelledby="delete-import-title"
        onCancel={(event) => {
          event.preventDefault();
          if (!busy) onCancel();
        }}
      >
        <h2 id="delete-import-title">Eliminar importación</h2>
        {selected && (
          <>
            <p>
              Carga{' '}
              <b>
                #{selected.id} · {selected.filename}
              </b>
            </p>
            <p>
              {selected.entry_count} partidas · {selected.currency} · {periods(selected)}
            </p>
            <p>
              Se eliminarán únicamente esta carga y sus partidas. El resumen, los presupuestos y el
              forecast usarán los datos restantes. Comprueba el número de carga, incluso si hay
              archivos con el mismo nombre.
            </p>
            <p className="muted">
              Después podrás importar el archivo definitivo, siempre que no entre en conflicto con
              otras partidas que permanezcan guardadas.
            </p>
            <label>
              Escribe <b>{code}</b> para confirmar
              <input
                autoComplete="off"
                spellCheck={false}
                value={confirmation}
                disabled={busy}
                onChange={(event) => onConfirmation(event.target.value)}
              />
            </label>
          </>
        )}
        {deleteError && (
          <p className="error" role="alert">
            {deleteError}
          </p>
        )}
        <div className="scenario-actions">
          <button className="secondary" autoFocus disabled={busy} onClick={onCancel}>
            Cancelar
          </button>
          <button
            className="delete-button"
            disabled={busy || !selected || confirmation !== code}
            onClick={onDelete}
          >
            {busy ? 'Eliminando…' : 'Eliminar definitivamente'}
          </button>
        </div>
      </dialog>
    </article>
  );
}

export default function ImportHistory({
  revision,
  onDeleted,
  busy = false,
  onBusyChange,
  request = api,
}) {
  const [page, setPage] = useState({ items: [], total: 0, limit: 25, offset: 0 });
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [confirmation, setConfirmation] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [deleting, setDeleting] = useState(false);
  const dialog = useRef(null);
  const locked = busy || deleting;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError('');
    request(`/financial/imports?limit=25&offset=${offset}`, { signal: controller.signal })
      .then((value) => {
        if (active) setPage(value);
      })
      .catch((reason) => {
        if (active) setError(reason.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [offset, reload, revision, request]);

  useEffect(() => {
    if (selected) dialog.current?.showModal();
    else dialog.current?.close();
  }, [selected]);

  function cancel() {
    if (locked) return;
    setSelected(null);
    setConfirmation('');
    setDeleteError('');
  }

  async function remove() {
    if (locked || !selected || confirmation !== `ELIMINAR ${selected.id}`) return;
    setDeleting(true);
    onBusyChange?.(true);
    setDeleteError('');
    try {
      const result = await request(`/financial/imports/${selected.id}`, {
        method: 'DELETE',
        body: JSON.stringify({ confirmation, sha256: selected.sha256 }),
      });
      setSelected(null);
      setConfirmation('');
      if (page.items.length === 1 && offset > 0) setOffset(Math.max(0, offset - 25));
      setReload((value) => value + 1);
      onDeleted?.(result);
    } catch (reason) {
      setDeleteError(reason.message);
    } finally {
      setDeleting(false);
      onBusyChange?.(false);
    }
  }

  return (
    <ImportHistoryView
      page={page}
      loading={loading}
      error={error}
      busy={locked}
      selected={selected}
      confirmation={confirmation}
      deleteError={deleteError}
      onSelect={(batch) => {
        setSelected(batch);
        setConfirmation('');
        setDeleteError('');
      }}
      onConfirmation={setConfirmation}
      onCancel={cancel}
      onDelete={remove}
      onPage={setOffset}
      onReload={() => setReload((value) => value + 1)}
      dialogRef={dialog}
    />
  );
}
