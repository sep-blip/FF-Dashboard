import type { StatementAnalysis } from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export async function analyzeStatements(
  files: File[],
  options: {
    enableOcr: boolean;
    useAiClassifier: boolean;
  },
): Promise<StatementAnalysis> {
  const body = new FormData();
  for (const file of files) {
    body.append("files", file);
  }
  body.append("enable_ocr", String(options.enableOcr));
  body.append("use_ai_classifier", String(options.useAiClassifier));

  const response = await fetch(
    `${API_BASE_URL}/v1/documents/bank-statements/analyze`,
    {
      method: "POST",
      body,
    },
  );

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      payload?.detail ||
        `Statement analysis failed with HTTP ${response.status}`,
    );
  }

  return response.json() as Promise<StatementAnalysis>;
}
