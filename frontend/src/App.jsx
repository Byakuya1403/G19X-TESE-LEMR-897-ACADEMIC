import React, { useEffect, useState, useRef } from 'react';
import Simulation from './Simulation';
import Activation from './Activation';
import Users from './Users';
import Dashboard from './components/Dashboard';
import Importaciones from './components/Importaciones';
import Login from './components/Login';
import { api } from './services/api';
import { formatMoney, monthLabel } from './utils/formatters';
import { descriptions, roles } from './constants';

function consumeActivationToken() {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('activar');
  if (token !== null) {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }
  return token;
}
const initialActivation = consumeActivationToken();

export default function App() {
  const [activation, setActivation] = useState(initialActivation);
  const [currency, setCurrency] = useState('MXN');
  const [repair, setRepair] = useState(false);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  function money(value) {
    return formatMoney(value, currency);
  }
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [authBusy, setAuthBusy] = useState(false);
  const dialog = useRef(null);
  const openLoginAfterActivation = useRef(false);
  useEffect(() => {
    if (activation === null && authReady && openLoginAfterActivation.current) {
      openLoginAfterActivation.current = false;
      dialog.current?.showModal();
    }
  }, [activation, authReady]);
  useEffect(() => {
    const opened = () => {
      const token = consumeActivationToken();
      if (token !== null) setActivation(token);
    };
    window.addEventListener('hashchange', opened);
    return () => window.removeEventListener('hashchange', opened);
  }, []);
  useEffect(() => {
    if (activation !== null) return;
    let active = true;
    setAuthReady(false);
    api('/auth/me')
      .then((v) => {
        if (active) setUser(v);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setAuthReady(true);
      });
    return () => {
      active = false;
    };
  }, [activation]);
  async function signIn(e) {
    e.preventDefault();
    setLoginError('');
    setAuthBusy(true);
    try {
      const values = Object.fromEntries(new FormData(e.target));
      const account = await api('/auth/login', { method: 'POST', body: JSON.stringify(values) });
      setUser(account);
      setDepartment('');
      setData(null);
      setAll([]);
      setPreview(null);
      setFile(null);
      setPage('Resumen');
      setNotice('');
      dialog.current.close();
      e.target.reset();
      setRefresh((v) => v + 1);
    } catch (e) {
      setLoginError(e.message);
    } finally {
      setAuthBusy(false);
    }
  }
  async function signOut() {
    setAuthBusy(true);
    try {
      await api('/auth/logout', { method: 'POST' });
      setUser(null);
      setPage('Resumen');
      setDepartment('');
      setAll([]);
      setData(null);
      setPreview(null);
      setFile(null);
      setNotice('');
      setRefresh((v) => v + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setAuthBusy(false);
    }
  }
  const [page, setPage] = useState('Resumen');
  const [all, setAll] = useState([]);
  const [period, setPeriod] = useState('2026-01');
  const [department, setDepartment] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!authReady || activation !== null) return;
    let active = true;
    setLoading(true);
    setError('');
    Promise.all([
      api('/financial/entries'),
      api(
        '/financial/dashboard?' +
          new URLSearchParams({
            period,
            currency,
            ...(department ? { category: department } : {}),
          }),
      ),
    ])
      .then(([entries, dashboard]) => {
        if (active) {
          setAll(entries);
          setData(dashboard);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [period, department, refresh, authReady, user, currency, activation]);
  const allowed =
    user?.role === 'director'
      ? ['Resumen', 'Presupuestos', 'Simulación']
      : user?.role === 'analyst'
        ? ['Resumen', 'Presupuestos', 'Simulación', 'Importaciones']
        : user?.role === 'admin'
          ? ['Resumen', 'Usuarios']
          : ['Resumen'];
  const categories = [
    ...new Set(all.filter((x) => x.currency === currency).map((x) => x.category)),
  ];
  async function inspect() {
    if (!file) return;
    setBusy(true);
    setError('');
    setPreview(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('repair_shifted', String(repair));
      setPreview(await api('/financial/imports/preview', { method: 'POST', body: formData }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function upload() {
    if (!file || !preview) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('currency', currency);
      formData.append('repair_shifted', String(repair));
      const imported = await api('/financial/imports/csv', { method: 'POST', body: formData });
      setNotice(
        `${imported.imported} partidas importadas. ${imported.warnings.length} reparaciones confirmadas.`,
      );
      setPeriod(imported.periods.at(-1));
      setDepartment('');
      setRefresh((v) => v + 1);
      setFile(null);
      setPreview(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function importedDataDeleted(result) {
    setPreview(null);
    setFile(null);
    setDepartment('');
    setNotice(
      `${result.deleted_entries} partidas de ${result.filename} eliminadas. El resumen y el forecast se recalcularán con los datos restantes.`,
    );
    setRefresh((value) => value + 1);
  }

  async function finishActivation(openLogin) {
    if (openLogin) {
      await api('/auth/logout', { method: 'POST' });
      setUser(null);
      setPage('Resumen');
      setAll([]);
      setData(null);
      setDepartment('');
      setNotice('');
      setError('');
    }
    openLoginAfterActivation.current = openLogin;
    setActivation(null);
  }
  if (activation !== null)
    return (
      <Activation
        key={activation}
        token={activation}
        request={api}
        roles={roles}
        onFinish={finishActivation}
      />
    );
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="#">
          ◈{' '}
          <span>
            Presupuesto<small>FINANZAS CORPORATIVAS</small>
          </span>
        </a>
        <div className="navlabel">ESPACIO FINANCIERO</div>
        <nav>
          {allowed.map((x, i) => (
            <button
              className={page === x ? 'active' : ''}
              onClick={() => {
                setPage(x);
                setNotice('');
              }}
              key={x}
            >
              <span>{['▦', '▤', '↗', '⇧', '◫'][i]}</span>
              {x}
            </button>
          ))}
        </nav>
        <div className="asidefoot">
          <span className="dot" /> Entorno de desarrollo
          <small>{user ? roles[user.role] : 'Vista de demostración'}</small>
        </div>
      </aside>
      <main>
        <header>
          <div>
            Planeación / <b>{page}</b>
          </div>
          <div className="sessioncontrols">
            {user ? (
              <>
                <span className="badge">
                  {user.email || user.username} · {roles[user.role]}
                </span>
                <button disabled={authBusy} onClick={signOut}>
                  Cerrar sesión
                </button>
              </>
            ) : (
              <button
                disabled={!authReady}
                onClick={() => {
                  setLoginError('');
                  dialog.current.showModal();
                }}
              >
                Iniciar sesión
              </button>
            )}
          </div>
        </header>
        <section className="content">
          <div className="heading">
            <div>
              <p className="eyebrow">CONTROL PRESUPUESTARIO</p>
              <h1>{page === 'Resumen' ? 'Una visión clara de tus recursos.' : page}</h1>
              <p className="subtitle">{descriptions[page]}</p>
            </div>
            <div className="filters">
              <label>
                Moneda
                <select
                  value={currency}
                  onChange={(e) => {
                    setCurrency(e.target.value);
                    setDepartment('');
                    setPreview(null);
                  }}
                >
                  {[
                    ...new Set([
                      'MXN',
                      'USD',
                      'EUR',
                      ...all.map((r) => r.currency).filter(Boolean),
                    ]),
                  ].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label>
                Periodo
                <input
                  type="month"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                  required
                />
              </label>
              <label>
                Categoría
                <select value={department} onChange={(e) => setDepartment(e.target.value)}>
                  <option value="">Todos</option>
                  {categories.map((d) => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          {data?.demo && (
            <div className="notice">
              Datos de demostración.{' '}
              {user
                ? 'El rol administrativo gestiona cuentas; la información financiera real requiere un rol financiero.'
                : 'Inicia sesión para acceder a la información real y a las acciones de tu rol.'}
            </div>
          )}
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          {notice && (
            <div role="status" className="notice">
              {notice}
            </div>
          )}
          {loading && <p role="status">Cargando información…</p>}
          {page === 'Resumen' && data && !loading && (
            <Dashboard
              data={data}
              entries={all}
              currency={currency}
              category={department}
              period={period}
              user={user}
              onPeriodChange={setPeriod}
              onImport={() => setPage('Importaciones')}
            />
          )}

          {page === 'Presupuestos' && (
            <article className="panel">
              <h2>Partidas del presupuesto</h2>
              <p className="muted">
                Detalle por concepto. No se asigna un departamento cuando el archivo no lo contiene.
              </p>
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Periodo</th>
                      <th>Categoría / concepto</th>
                      <th>Presupuesto</th>
                      <th>Real</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {all
                      .filter(
                        (r) =>
                          r.period === period &&
                          r.currency === currency &&
                          (!department || r.category === department),
                      )
                      .map((r) => (
                        <tr key={r.id}>
                          <td>{r.source_id}</td>
                          <td>{r.period}</td>
                          <td>
                            {r.category}
                            <br />
                            <small>{r.concept}</small>
                          </td>
                          <td>{money(r.budget)}</td>
                          <td>{money(r.actual)}</td>
                          <td>{r.status === 'pendiente' ? 'Pendiente' : 'Completado'}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <p className="note">
                Las partidas se incorporan desde Importaciones con una cuenta de Analista
                Financiero. Cada registro conserva la categoría, el concepto y el periodo del
                archivo.
              </p>
            </article>
          )}
          {page === 'Simulación' && (
            <Simulation
              key={`${period}:${currency}:${department}:${user?.username}:${refresh}`}
              entries={all}
              period={period}
              currency={currency}
              category={department}
              money={money}
              monthLabel={monthLabel}
              request={api}
              loading={loading}
            />
          )}
          {page === 'Importaciones' && (
            <Importaciones
              currency={currency}
              setCurrency={setCurrency}
              file={file}
              setFile={setFile}
              repair={repair}
              setRepair={setRepair}
              preview={preview}
              setPreview={setPreview}
              busy={busy}
              setError={setError}
              onInspect={inspect}
              onUpload={upload}
              revision={refresh}
              onDeleted={importedDataDeleted}
              onBusyChange={setBusy}
            />
          )}

          {page === 'Usuarios' && user?.role === 'admin' && (
            <Users request={api} roles={roles} currentUser={user} />
          )}
          <Login dialogRef={dialog} onSignIn={signIn} loginError={loginError} authBusy={authBusy} />
          <footer>
            Plataforma de Presupuesto / v0.18{' '}
            <span>{data?.demo ? 'Vista de demostración' : 'Sesión financiera'}</span>
          </footer>
        </section>
      </main>
    </div>
  );
}
