export const VENDOR_TOKEN_KEY = 'estateflow_vendor_token';

export function getVendorToken(): string | null {
  return localStorage.getItem(VENDOR_TOKEN_KEY);
}

export function setVendorToken(token: string): void {
  localStorage.setItem(VENDOR_TOKEN_KEY, token);
}

export function clearVendorToken(): void {
  localStorage.removeItem(VENDOR_TOKEN_KEY);
}

export function hasVendorToken(): boolean {
  return Boolean(getVendorToken());
}
