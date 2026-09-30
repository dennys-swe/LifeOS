import { describe, expect, it } from "vitest";

import {
  describeChange,
  groupBySeverity,
  issueCopy,
  KIND_COPY,
  openCountLabel,
  previewEffects,
  SEVERITY_LABEL,
} from "./dataQuality";

// Os cinco tipos que a auditoria do backend pode gerar (data_quality_service.ALL_KINDS).
const BACKEND_KINDS = [
  "system_says_transfer",
  "unmarked_mirror",
  "unlinked_reversal",
  "large_unusual_income",
  "uncategorized_expense",
];

const fmt = (n) => `R$ ${n.toFixed(2).replace(".", ",")}`;

describe("dataQuality", () => {
  it("tem texto para todos os tipos que o backend gera", () => {
    for (const kind of BACKEND_KINDS) {
      expect(KIND_COPY[kind], kind).toBeTruthy();
      expect(issueCopy(kind).title.length).toBeGreaterThan(0);
    }
  });

  it("tipo desconhecido cai num texto genérico em vez de quebrar", () => {
    expect(issueCopy("tipo_novo").title).toBe("Possível problema nos dados");
  });

  it("agrupa por gravidade, na ordem certa, sem grupos vazios", () => {
    const issues = [
      { id: "1", severity: "info" },
      { id: "2", severity: "high" },
      { id: "3", severity: "info" },
    ];

    const groups = groupBySeverity(issues);

    expect(groups.map((g) => g.severity)).toEqual(["high", "info"]);
    expect(groups[1].issues.map((i) => i.id)).toEqual(["1", "3"]);
    expect(SEVERITY_LABEL.high).toBe("Precisa de atenção");
  });

  it("descreve cada mudança da prévia", () => {
    expect(
      describeChange({ field: "is_transfer", description: "PAGAMENTO ON LINE", old: "false", new: "true" })
    ).toBe("Marcar como transferência: PAGAMENTO ON LINE");
    expect(
      describeChange({ field: "category_id", description: "PASTAS", old: "sem categoria", new: "Alimentação" })
    ).toBe('Categoria de "PASTAS": sem categoria → Alimentação');
  });

  it("só lista o efeito que existe", () => {
    expect(previewEffects({ income_removed: "769.01", expense_removed: "0.00" }, fmt)).toEqual([
      "Sai da renda: R$ 769,01",
    ]);
    expect(previewEffects({ income_removed: "0", expense_removed: "35.5" }, fmt)).toEqual([
      "Sai dos gastos: R$ 35,50",
    ]);
    expect(previewEffects({ income_removed: "0", expense_removed: "0" }, fmt)).toEqual([]);
  });

  it("usa singular e plural na contagem", () => {
    expect(openCountLabel(1)).toBe("1 possível erro nos seus dados");
    expect(openCountLabel(3)).toBe("3 possíveis erros nos seus dados");
  });
});
