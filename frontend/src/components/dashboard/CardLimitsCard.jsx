import { useEffect, useState } from "react";
import { Link } from "react-router";

import Card, { CardHeader } from "../ui/Card";
import Skeleton from "../ui/Skeleton";
import { usageTone } from "../../lib/cardLimits";
import { fmt } from "../../lib/format";
import api from "../../services/api";

const BAR = {
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
  slate: "bg-slate-400",
};

function UsageBar({ pct, className = "h-2" }) {
  const width = Math.min(Math.max(pct ?? 0, 0), 100);
  return (
    <div className={`w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800 ${className}`}>
      <div className={`h-full rounded-full ${BAR[usageTone(pct)]}`} style={{ width: `${width}%` }} />
    </div>
  );
}

// Só o que pode enganar vira aviso: dado parado e cartão que o banco não informa.
function notes(data) {
  const out = [];
  if (data.freshness_state === "stale" || data.freshness_state === "attention") {
    out.push({
      key: "stale",
      text: "Os dados de pelo menos uma conexão estão desatualizados, então o limite pode ter mudado.",
      link: true,
    });
  }
  if (data.cards_without_limit > 0) {
    out.push({
      key: "nolimit",
      text: `${data.cards_without_limit} cartão(ões) sem limite informado pelo banco ficaram fora da soma.`,
    });
  }
  if (data.cards_inconsistent > 0) {
    out.push({
      key: "inconsistent",
      text: `${data.cards_inconsistent} cartão(ões) com limite inconsistente ficaram fora da soma.`,
    });
  }
  if (data.cards_ignored > 0) {
    out.push({
      key: "ignored",
      text: `${data.cards_ignored} cartão(ões) marcado(s) como ignorado(s) não entram na soma.`,
    });
  }
  return out;
}

export default function CardLimitsCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .get("/cards/limits")
      .then((res) => {
        if (!cancelled) setData(res.data);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <Card className="p-6">
        <CardHeader title="Limite dos cartões" subtitle="usado e disponível" />
        <Skeleton className="h-16" />
      </Card>
    );
  }
  // Sem cartão com limite informado não há o que mostrar: não ocupa espaço.
  if (!data || (data.cards_counted === 0 && data.cards_without_limit === 0)) return null;

  const counted = data.cards.filter((c) => c.status === "ok");
  const tone = usageTone(data.used_pct);

  return (
    <Card className="p-6" data-testid="card-limits">
      <CardHeader title="Limite dos cartões" subtitle="usado e disponível" />

      {data.cards_counted > 0 ? (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-display text-2xl font-extrabold text-slate-900 dark:text-white">
              {fmt(Number(data.total_used))}
              <span className="ml-1 text-sm font-semibold text-slate-400">
                de {fmt(Number(data.total_limit))}
              </span>
            </p>
            <p className="text-sm font-bold text-slate-600 dark:text-slate-300" data-testid="card-limits-pct">
              {data.used_pct != null ? `${data.used_pct.toLocaleString("pt-BR")}% usado` : ""}
            </p>
          </div>
          <UsageBar pct={data.used_pct} className="mt-2 h-3" />
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Disponível:{" "}
            <span
              className={`font-bold ${tone === "rose" ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}
            >
              {fmt(Number(data.total_available))}
            </span>
          </p>

          {counted.length > 1 && (
            <ul className="mt-4 flex flex-col gap-3">
              {counted.map((card) => (
                <li key={card.pluggy_account_id}>
                  <div className="flex items-baseline justify-between gap-2 text-xs">
                    <span className="truncate font-semibold text-slate-700 dark:text-slate-200">
                      {card.label}
                    </span>
                    <span className="flex-shrink-0 text-slate-500 dark:text-slate-400">
                      {fmt(Number(card.used))} de {fmt(Number(card.credit_limit))}
                      {card.used_pct != null && ` · ${card.used_pct.toLocaleString("pt-BR")}%`}
                    </span>
                  </div>
                  <UsageBar pct={card.used_pct} className="mt-1 h-1.5" />
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Nenhum cartão informou o limite ainda.
        </p>
      )}

      <p className="mt-4 text-[11px] text-slate-400 dark:text-slate-500">
        O limite usado inclui parcelas futuras, por isso não é o valor da fatura.
      </p>
      {notes(data).map((n) => (
        <p key={n.key} className="mt-1 text-[11px] font-semibold text-amber-600 dark:text-amber-400">
          {n.text}
          {n.link && (
            <>
              {" "}
              <Link to="/banks" className="underline">
                Ver conexões
              </Link>
            </>
          )}
        </p>
      ))}
    </Card>
  );
}
