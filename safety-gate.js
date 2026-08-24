export function applySafetyGate(result){
  const r = result?.risk || {level:"unknown",confidence:0,reasons:[]};
  const blocked = r.level === "high" || r.level === "unknown" || r.confidence < 0.70;
  return {
    ...result,
    safety: {
      blocked_from_sensitive_action: blocked,
      rule: blocked
        ? "Do not enable payment, transfer, credential sharing, or irreversible actions."
        : "Still require explicit confirmation for sensitive actions."
    }
  };
}
