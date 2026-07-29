export type WrappedList<T = any> = {
  data: {
    results: T[];
    count: number;
  };
  status: 'success';
  message: string;
};

export type WrappedOne<T = any> = {
  data: T | null;
  status: 'success';
  message: string;
};

export function normalizeListPayload<T = any>(
  payload: any,
  fallbackTotal?: number
): { results: T[]; count: number } {
  let current = payload;
  let countHint = fallbackTotal;

  for (let i = 0; i < 5; i += 1) {
    if (Array.isArray(current)) {
      return { results: current, count: countHint ?? current.length };
    }

    if (!current || typeof current !== 'object') {
      break;
    }

    if (typeof current.count === 'number') {
      countHint = current.count;
    }

    if (Array.isArray(current.results)) {
      return { results: current.results, count: countHint ?? current.results.length };
    }

    if (Array.isArray(current.data)) {
      return { results: current.data, count: countHint ?? current.data.length };
    }

    if (current.data && typeof current.data === 'object' && current.data !== current) {
      current = current.data;
      continue;
    }

    if (current.results && typeof current.results === 'object' && current.results !== current) {
      current = current.results;
      continue;
    }

    break;
  }

  return { results: [], count: countHint ?? 0 };
}

export function throwIfFailed(res: any): void {
  if (!res.success) {
    const err: any = new Error(res.error || res.message || '操作失败');
    err.errors = res.errors;
    throw err;
  }
}

export function wrapListResponse<T = any>(res: any): WrappedList<T> {
  throwIfFailed(res);

  const { results, count } = normalizeListPayload<T>(res.data, res.total);
  return { data: { results, count }, status: 'success', message: '' };
}

export function wrapOneResponse<T = any>(res: any): WrappedOne<T> {
  throwIfFailed(res);

  return { data: res.data ?? null, status: 'success', message: '' };
}

export function toArray<T = any>(value: unknown): T[] {
  return normalizeListPayload<T>(value).results;
}
