import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import { App } from "./app";

const IN = { setup_required: false, logged_in: true, username: "admin" };

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("renders_shell_routes", async () => {
    mockFetch({ "GET /api/auth/status": jsonResponse(IN) });
    renderAt("/shops");
    expect(await screen.findByRole("heading", { name: "店铺" })).toBeInTheDocument();
  });

  it("redirects_root_to_orders", async () => {
    mockFetch({ "GET /api/auth/status": jsonResponse(IN) });
    renderAt("/");
    expect(await screen.findByRole("heading", { name: "订单" })).toBeInTheDocument();
  });

  it("未登录时进入登录页", async () => {
    mockFetch({ "GET /api/auth/status": jsonResponse({ setup_required: false, logged_in: false, username: null }) });
    renderAt("/shops");
    expect(await screen.findByRole("button", { name: "登录" })).toBeInTheDocument();
  });
});
