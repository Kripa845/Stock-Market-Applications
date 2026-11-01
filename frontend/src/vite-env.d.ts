/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  /** "1" under `npm run dev` serves generated Stock Comparison payloads (api/compareMock.ts). */
  readonly VITE_COMPARE_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
