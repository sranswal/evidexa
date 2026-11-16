import { request } from "./client";

export interface AiModelOption {
  id: string;
  name: string;
  capabilities: string[];
}

export interface AiConfigData {
  mode: "OFFLINE" | "ONLINE";
  provider: string;
  model: string;
  has_key: boolean;
  masked_key: string | null;
  is_validated: boolean;
  validation_message: string | null;
  last_validated_at: string | null;
  last_latency_ms: number | null;
  available_models: AiModelOption[];
}

export interface UpdateAiConfigRequest {
  mode: "OFFLINE" | "ONLINE";
  provider?: string;
  model: string;
  api_key?: string | null;
  validate?: boolean;
}

export interface TestAiKeyResponse {
  success: boolean;
  latency_ms?: number;
  model?: string;
  message?: string;
  error?: string;
  sample_reply?: string;
}

export const aiConfigApi = {
  getConfig: (): Promise<AiConfigData> => request<AiConfigData>("/system/ai-config"),

  updateConfig: (
    data: UpdateAiConfigRequest
  ): Promise<{ success: boolean; config: AiConfigData; error?: string }> =>
    request<{ success: boolean; config: AiConfigData; error?: string }>("/system/ai-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  testKey: (apiKey: string, model = "gemini-2.5-flash"): Promise<TestAiKeyResponse> =>
    request<TestAiKeyResponse>("/system/ai-config/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey, model }),
    }),
};
