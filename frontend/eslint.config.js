import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

// 分层守门（engineering-rules 2.1）：
//   logic/**      不得 import react
//   components/** 不得 import @/lib/api-client
// 第三方源码（components/arc）与生成文件（lib/api-types.ts）不参与 lint。
export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/components/arc/**", "src/lib/api-types.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-hooks": reactHooks },
    rules: reactHooks.configs.recommended.rules,
  },
  {
    files: ["src/pages/*/logic/**/*.{ts,tsx}", "src/components/custom/*/logic/**/*.{ts,tsx}"],
    ignores: ["**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            { group: ["react", "react/*", "react-dom", "react-dom/*"], message: "logic/ 是纯函数层，不得 import react" },
          ],
        },
      ],
    },
  },
  {
    files: ["src/pages/*/components/**/*.{ts,tsx}", "src/components/custom/*/components/**/*.{ts,tsx}"],
    ignores: ["**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            { group: ["@/lib/api-client", "**/lib/api-client"], message: "components/ 是纯展示层，不得调用接口，数据由 hooks 注入" },
          ],
        },
      ],
    },
  },
);
