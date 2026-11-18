// Central API configuration for IntelliWatch.
// Supports same-origin deployment and explicit API origins.

const configuredApiUrl = (
    import.meta.env.VITE_API_URL ?? ""
).trim();

export const API_BASE =
    configuredApiUrl === "/"
        ? ""
        : configuredApiUrl.replace(/\/+$/, "");

export function apiUrl(path = "") {
    const cleanPath = String(path).replace(/^\/+/, "");
    return cleanPath
        ? `${API_BASE}/${cleanPath}`
        : API_BASE || "/";
}

export function wsUrl(path = "") {
    const cleanPath = String(path).replace(/^\/+/, "");

    const baseUrl = new URL(
        API_BASE || window.location.origin,
        window.location.origin
    );

    baseUrl.protocol =
        baseUrl.protocol === "https:" ? "wss:" : "ws:";

    baseUrl.pathname = [
        baseUrl.pathname.replace(/\/+$/, ""),
        cleanPath
    ].filter(Boolean).join("/");

    baseUrl.search = "";
    baseUrl.hash = "";

    return baseUrl.toString();
}
