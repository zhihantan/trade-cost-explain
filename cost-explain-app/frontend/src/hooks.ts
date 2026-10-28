import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "./api/client";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: 5 * 60_000 });
}

export function useComparisons() {
  return useQuery({ queryKey: ["comparisons"], queryFn: api.comparisons, staleTime: 5 * 60_000 });
}

// "MOM_2026-09" -> "Sep 2026 vs Aug 2026" once the comparison list has loaded (the id until then).
export function useComparisonLabel(): (id: string) => string {
  const comps = useComparisons();
  return (id) => {
    const c = comps.data?.find((x) => x.comparison_id === id);
    return c ? c.comparison_label ?? `${c.p1_label} vs ${c.p0_label}` : id;
  };
}

// True once `active` has stayed true for `ms` — used to explain a slow first load (warehouse waking up).
export function useSlow(active: boolean, ms = 4000): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!active) {
      setSlow(false);
      return;
    }
    const t = window.setTimeout(() => setSlow(true), ms);
    return () => window.clearTimeout(t);
  }, [active, ms]);
  return slow;
}
