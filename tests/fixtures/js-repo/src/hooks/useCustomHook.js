import { useState, useEffect } from 'react';

export function useCustomHook() {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setValue(v => v + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return value;
}

export function useAnotherHook(dep) {
  const [result, setResult] = useState(null);

  useEffect(() => {
    setResult(`processed-${dep}`);
  }, [dep]);

  return result;
}
