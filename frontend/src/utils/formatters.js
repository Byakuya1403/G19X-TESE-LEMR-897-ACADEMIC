export function formatMoney(value, currency = 'MXN') {
  if (value === null || value === undefined) {
    return 'Pendiente';
  }
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export function monthLabel(period) {
  if (!period) {
    return 'Sin periodo disponible';
  }
  return new Intl.DateTimeFormat('es-MX', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${period}-01T00:00:00Z`));
}
