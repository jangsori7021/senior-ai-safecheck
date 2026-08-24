// Provider boundary: secrets/API keys must never be embedded in the client.
export async function analyzeImage({imageFile, mode, voiceContext=""}) {
  // Production: POST multipart/form-data to your HTTPS backend.
  // Backend selects the configured vision model and validates its JSON output
  // against analysis_contract.schema.json.
  throw new Error("AI_PROVIDER_NOT_CONFIGURED");
}
