
export function selectAgent(message) {
  if (message.startsWith("/pro")) return "pro";
  if (message.startsWith("/fast")) return "fast";
  return "default";
}
