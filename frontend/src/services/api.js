const fieldLabels = {
  username: 'Correo o usuario',
  email: 'Correo',
  password: 'Contraseña',
  confirmation: 'Confirmación',
  role: 'Rol',
  token: 'Enlace de activación',
};

function errorMessage(detail) {
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((issue) => {
        const field = issue.loc?.at(-1);
        const label = fieldLabels[field] || field || 'Campo';
        return `${label}: ${issue.msg}`;
      })
      .join('. ');
  }
  return 'No se pudo completar la solicitud';
}

export async function api(path, options) {
  const isFormData = options?.body instanceof FormData;
  const response = await fetch('/api' + path, {
    ...options,
    credentials: 'include',
    headers: {
      ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
      'X-App': '1',
      ...options?.headers,
    },
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(errorMessage(data.detail));
  }
  return data;
}
