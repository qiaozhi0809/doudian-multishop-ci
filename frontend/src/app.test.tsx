import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "./app";

describe("App", () => {
  it("renders_shell_routes", () => {
    render(
      <MemoryRouter initialEntries={["/shops"]}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "店铺" })).toBeInTheDocument();
  });

  it("redirects_root_to_orders", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "订单" })).toBeInTheDocument();
  });
});
