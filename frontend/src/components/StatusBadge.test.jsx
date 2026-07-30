import React from 'react';
import { render, screen } from "@testing-library/react";

import StatusBadge from "./StatusBadge";

// Assert em texto/precedência, não em classe Tailwind literal — a classe
// exata muda toda vez que o componente é reestilizado (ex: suporte a tema
// claro), e isso não é o que o teste quer garantir.
describe("StatusBadge", () => {
  it("mostra PAGO quando status é PAID", () => {
    render(<StatusBadge status="PAID" isOverdue={false} isDueToday={false} />);
    expect(screen.getByText("PAGO")).toBeInTheDocument();
  });

  it("mostra ATRASADA quando pendente e vencida", () => {
    render(<StatusBadge status="PENDING" isOverdue isDueToday={false} />);
    expect(screen.getByText("ATRASADA")).toBeInTheDocument();
  });

  it("mostra VENCE HOJE quando pendente e vence hoje", () => {
    render(<StatusBadge status="PENDING" isOverdue={false} isDueToday />);
    expect(screen.getByText("VENCE HOJE")).toBeInTheDocument();
  });

  it("PAID tem precedência sobre atrasada/vence hoje", () => {
    render(<StatusBadge status="PAID" isOverdue isDueToday />);
    expect(screen.getByText("PAGO")).toBeInTheDocument();
    expect(screen.queryByText("ATRASADA")).not.toBeInTheDocument();
  });

  it("não renderiza nada quando pendente, sem atraso e não vence hoje", () => {
    const { container } = render(
      <StatusBadge status="PENDING" isOverdue={false} isDueToday={false} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
