import React from 'react';
import { render, screen } from "@testing-library/react";

import StatusBadge from "./StatusBadge";

describe("StatusBadge", () => {
  it("mostra o badge PAGO com classe verde", () => {
    render(<StatusBadge status="PAID" isOverdue={false} isDueToday={false} />);
    const badge = screen.getByText("PAGO");
    expect(badge).toHaveClass("text-emerald-300");
  });

  it("mostra o badge ATRASADA com classe vermelha", () => {
    render(<StatusBadge status="PENDING" isOverdue isDueToday={false} />);
    const badge = screen.getByText("ATRASADA");
    expect(badge).toHaveClass("text-rose-300");
  });

  it("mostra o badge VENCE HOJE com classe amarela", () => {
    render(<StatusBadge status="PENDING" isOverdue={false} isDueToday />);
    const badge = screen.getByText("VENCE HOJE");
    expect(badge).toHaveClass("text-amber-300");
  });
});