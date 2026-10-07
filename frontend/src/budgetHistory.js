// Income and expense rows remain separate; date/category/currency are actual filters.
export function budgetHistory(entries, currency, category = '', period = '') {
  const periods = new Map();
  for (const entry of entries) {
    if (entry.currency !== currency || (period && entry.period !== period) || (category && entry.category !== category)) continue;
    if (!periods.has(entry.period)) periods.set(entry.period, new Map());
    const categories = periods.get(entry.period);
    const key = `${entry.nature}:${entry.category}`;
    if (!categories.has(key)) categories.set(key, {category: entry.category, nature: entry.nature, budget: 0, known: 0, pending: 0});
    const row = categories.get(key);
    row.budget += entry.budget;
    if (entry.actual === null) row.pending += 1;
    else row.known += entry.actual;
  }
  return [...periods].sort(([a],[b])=>b.localeCompare(a)).map(([period, categories])=>({
    period,
    categories: [...categories.values()].sort((a,b)=>a.category.localeCompare(b.category)).map(row=>({
      ...row,
      actual: row.pending ? null : row.known,
      utilization: row.pending || !row.budget ? null : row.known / row.budget * 100,
    })),
  }));
}
