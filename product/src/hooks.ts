import { useEffect, useState } from "react";

// Minimal async-data hook: runs the loader when its dependencies change and tracks loading/error/value.
// Keeps components free of repetitive fetch boilerplate.
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    loader()
      .then((v) => alive && setValue(v))
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => alive && setLoading(false));

    return () => {
      alive = false;
    };
    
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { value, error, loading };
}
