/** Format a number as a percentage string. */
export function pct(n: number): string {
  return `${Math.round(n)}%`;
}

/** Truncate a string to maxLen characters, adding ellipsis. */
export function truncate(str: string, maxLen: number): string {
  if (!str) return "";
  return str.length > maxLen ? str.slice(0, maxLen) + "…" : str;
}

/** Join an array of strings, handling empty/null values. */
export function joinNonEmpty(arr: string[], sep = ", "): string {
  return arr.filter(Boolean).join(sep);
}
