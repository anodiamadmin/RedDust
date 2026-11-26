function requiredHttps(name: string, value?: string): string {
  if (!value?.trim()) throw new Error(`${name} is missing`);
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error(`${name} must be a valid HTTPS URL`);
  }
  if (
    url.protocol !== "https:" ||
    !url.hostname ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/" ||
    ["localhost", "127.0.0.1"].includes(url.hostname) ||
    url.hostname.endsWith(".invalid")
  ) {
    throw new Error(`${name} must be a trusted HTTPS base URL`);
  }
  return url.origin;
}
export const AUTH_BASE = requiredHttps(
  "EXPO_PUBLIC_AUTH_API_URL",
  process.env.EXPO_PUBLIC_AUTH_API_URL,
);
export const GATEWAY_BASE = requiredHttps(
  "EXPO_PUBLIC_GATEWAY_URL",
  process.env.EXPO_PUBLIC_GATEWAY_URL,
);
export const WEB_CLIENT_ID =
  process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID?.trim();
if (!WEB_CLIENT_ID?.endsWith(".apps.googleusercontent.com")) {
  throw new Error("Missing or invalid Google Web client ID");
}
