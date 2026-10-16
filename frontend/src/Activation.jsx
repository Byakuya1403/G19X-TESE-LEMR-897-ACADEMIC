import React, { useEffect, useState } from 'react';

export default function Activation({ token, request, roles, onFinish }) {
  const [info, setInfo] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [done, setDone] = useState(false),
    [show, setShow] = useState(false);
  useEffect(() => {
    let active = true;
    request('/auth/invitation/validate', { method: 'POST', body: JSON.stringify({ token }) })
      .then((v) => {
        if (active) setInfo(v);
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
  }, [token, request]);
  async function submit(e) {
    e.preventDefault();
    const form = e.currentTarget;
    const fields = Object.fromEntries(new FormData(form));
    setError('');
    if (fields.password !== fields.confirmation) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setBusy(true);
    try {
      await request('/auth/activate', {
        method: 'POST',
        body: JSON.stringify({ token, ...fields }),
      });
      form.reset();
      setDone(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function finish(openLogin) {
    setBusy(true);
    setError('');
    try {
      await onFinish(openLogin);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="activation-screen">
      <article className="panel activation-card">
        <p className="eyebrow">PLATAFORMA DE PRESUPUESTO</p>
        <h1>{done ? 'Tu cuenta está activada' : 'Crea tu contraseña'}</h1>
        {loading ? (
          <p role="status">Comprobando invitación…</p>
        ) : done ? (
          <>
            <p>
              Ya puedes iniciar sesión con <b>{info.email}</b> y la contraseña que elegiste.
            </p>
            <button disabled={busy} onClick={() => finish(true)}>
              Ir al inicio de sesión
            </button>
          </>
        ) : info ? (
          <>
            <p>
              Invitación para <b>{info.email}</b>
            </p>
            <span className="badge">{roles[info.role]}</span>
            <p className="muted">
              Define una contraseña exclusiva para esta plataforma. No escribas la contraseña de tu
              correo. El enlace vence el {new Date(info.expires * 1000).toLocaleString('es-MX')}.
            </p>
            <form onSubmit={submit}>
              <fieldset disabled={busy}>
                <label>
                  Nueva contraseña
                  <input
                    name="password"
                    type={show ? 'text' : 'password'}
                    minLength={12}
                    maxLength={128}
                    autoComplete="new-password"
                    required
                    aria-describedby="password-policy"
                  />
                </label>
                <small id="password-policy">
                  Entre 12 y 128 caracteres. Puedes usar una frase larga y fácil de recordar.
                </small>
                <label>
                  Confirmar contraseña
                  <input
                    name="confirmation"
                    type={show ? 'text' : 'password'}
                    minLength={12}
                    maxLength={128}
                    autoComplete="new-password"
                    required
                  />
                </label>
                <label className="checklabel">
                  <input
                    type="checkbox"
                    checked={show}
                    onChange={(e) => setShow(e.target.checked)}
                  />
                  Mostrar contraseñas
                </label>
                <button>{busy ? 'Activando…' : 'Guardar contraseña y activar cuenta'}</button>
              </fieldset>
            </form>
            <p className="muted">
              No compartas este enlace. Si recargas esta página, vuelve a abrirlo desde tu correo.
            </p>
          </>
        ) : (
          <>
            <p>Solicita al administrador una nueva invitación.</p>
            <button className="secondary" disabled={busy} onClick={() => finish(false)}>
              Volver a la plataforma
            </button>
          </>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </article>
    </main>
  );
}
