import { useEffect, useState } from "react";
import { Link } from "react-router";

import { openCountLabel } from "../../lib/dataQuality";
import api from "../../services/api";

// Aviso discreto no dashboard: só aparece quando há algo aberto, e falha em silêncio.
export default function DataQualityBanner() {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get("/data-quality/summary")
      .then((res) => {
        if (!cancelled) setSummary(res.data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!summary || summary.open_total === 0) return null;

  const urgent = summary.by_severity?.high > 0;
  const tone = urgent
    ? "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300"
    : "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";

  return (
    <Link
      to="/data-quality"
      data-testid="data-quality-banner"
      className={`flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-xs font-semibold transition hover:brightness-105 ${tone}`}
    >
      <span>
        {openCountLabel(summary.open_total)}
        {urgent && ` (${summary.by_severity.high} pedem atenção)`}
      </span>
      <span className="font-bold underline">Conferir</span>
    </Link>
  );
}
