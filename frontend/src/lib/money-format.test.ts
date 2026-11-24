import { formatCents } from "./money-format";

describe("formatCents", () => {
  it.each([
    [0, "¥0.00"],
    [1, "¥0.01"],
    [99, "¥0.99"],
    [100, "¥1.00"],
    [123456, "¥1,234.56"],
    [100000000, "¥1,000,000.00"],
    [-500, "-¥5.00"],
    [-1, "-¥0.01"],
    [-123456, "-¥1,234.56"],
  ])("format_cents_cases: %d -> %s", (cents, expected) => {
    expect(formatCents(cents)).toBe(expected);
  });
});
