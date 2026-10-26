import { useCallback, useEffect, useRef, useState } from 'react';
import {
  brokerAccumulationApi, type AccumulationQuery, type BrokerFlow, type BrokerSignal, type BrokerSummary,
} from '../api/brokerAccumulation';

// Data hook for the broker accumulation section: signal, per-broker table and daily flow
// for one stock and range, loaded together.  A response for an older range is dropped.

export interface BrokerAccumulationData {
  signal: BrokerSignal;
  summary: BrokerSummary;
  flow: BrokerFlow;
}

export function useBrokerAccumulation(query: AccumulationQuery) {
  const [data, setData] = useState<BrokerAccumulationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const latest = useRef(0);
  const key = JSON.stringify(query);

  const load = useCallback(() => {
    const id = ++latest.current;
    const current = JSON.parse(key) as AccumulationQuery;
    setLoading(true);
    setError('');
    Promise.all([
      brokerAccumulationApi.signal(current),
      brokerAccumulationApi.summary(current),
      brokerAccumulationApi.flow(current),
    ])
      .then(([signal, summary, flow]) => { if (id === latest.current) setData({ signal, summary, flow }); })
      .catch((err: unknown) => {
        if (id !== latest.current) return;
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(detail ?? 'Unable to load broker accumulation data.');
      })
      .finally(() => { if (id === latest.current) setLoading(false); });
  }, [key]);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}
