export function advanceCalendarPeriod(cursor, view, direction) {
  if (!(cursor instanceof Date) || Number.isNaN(cursor.getTime())) {
    throw new TypeError('cursor must be a valid Date');
  }
  if (!Number.isInteger(direction) || direction === 0) {
    throw new TypeError('direction must be a non-zero integer');
  }
  const next = new Date(cursor);
  if (view === 'week') {
    next.setDate(next.getDate() + direction * 7);
    return next;
  }
  if (view !== 'month') throw new TypeError('view must be month or week');
  const day = next.getDate();
  next.setDate(1);
  next.setMonth(next.getMonth() + direction);
  const lastDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate();
  next.setDate(Math.min(day, lastDay));
  return next;
}
