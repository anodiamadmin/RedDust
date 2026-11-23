function requiredHttps(name: string, value?: string): string {
  if (!value?.trim()) {
    throw new Error(`${name} is missing`);
  }

  const base = value.trim();

  let parsed: URL;

  try {
    parsed = new URL(base);
  } catch {
    throw new Error(`${name} must be a valid HTTPS base URL`);
  }

  if (
    parsed.protocol !== "https:" ||
    !parsed.hostname ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(`${name} must be a valid HTTPS base URL`);
  }

  return base.replace(/\/+$/, "");
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

if (!WEB_CLIENT_ID) {
  throw new Error("Missing Google Web client ID");
}
