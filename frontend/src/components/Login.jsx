import React from 'react';

export default function Login({ dialogRef, onSignIn, loginError, authBusy }) {
  return (
    <dialog ref={dialogRef} className="loginDialog">
      <div className="paneltitle">
        <h2>Iniciar sesión</h2>
        <button
          type="button"
          aria-label="Cerrar inicio de sesión"
          onClick={() => dialogRef.current.close()}
        >
          ✕
        </button>
      </div>
      <p className="muted">
        Accede con tu correo y la contraseña que elegiste. Las cuentas anteriores pueden seguir
        usando su usuario.
      </p>
      <form onSubmit={onSignIn}>
        <label>
          Correo electrónico o usuario anterior
          <input
            name="username"
            autoComplete="username"
            maxLength="254"
            placeholder="persona@empresa.com"
            autoFocus
            required
          />
        </label>
        <label>
          Contraseña
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            maxLength="128"
            required
          />
        </label>
        {loginError && (
          <p role="alert" className="error">
            {loginError}
          </p>
        )}
        <button disabled={authBusy}>{authBusy ? 'Validando…' : 'Entrar'}</button>
      </form>
    </dialog>
  );
}
