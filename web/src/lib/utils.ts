import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Throw a formatted Error for a failed fetch response using its raw text body (no JSON parsing). */
export async function throwFetchError(res: Response, action: string): Promise<never> {
  const text = await res.text().catch(() => '');
  throw new Error(`${action} (${res.status}): ${text || res.statusText}`);
}

/** Read a failed response's body as text, and its `{ error }` field if the body is JSON. */
export async function readApiError(res: Response): Promise<{ text: string; message?: string }> {
  const text = await res.text().catch(() => '');
  let message: string | undefined;
  try {
    const parsed = JSON.parse(text) as { error?: string };
    message = parsed.error;
  } catch {
    message = undefined;
  }
  return { text, message };
}

/** Throw a formatted Error for a failed fetch response, preferring its JSON `{ error }` field over raw text. */
export async function throwApiError(res: Response, action: string): Promise<never> {
  const { text, message } = await readApiError(res);
  throw new Error(message || `${action} (status ${res.status}): ${text || res.statusText}`);
}
