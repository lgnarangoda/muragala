// Shared state for the simulated phone, guardian and ATM pages. The three pages
// run in one browser (tabs or windows) and pass the demo token, the alert and the
// held withdrawal through localStorage, standing in for push notifications.
// Every score and decision comes from the real API.
import { useEffect, useState } from 'react';
import { API } from './api.js';

export const TOKEN_KEY = 'demoToken';
export const ALERT_KEY = 'demoAlert';
export const COSIGN_KEY = 'demoCosign';

export function readJson(key) {
  try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch { return null; }
}

export function writeJson(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch { /* ignore */ }
}

// A fresh token per demo run, so earlier runs never change the score.
export function demoToken() {
  let t = readJson(TOKEN_KEY);
  if (!t) {
    t = `demo-amma-${Math.random().toString(36).slice(2, 6)}`;
    writeJson(TOKEN_KEY, t);
  }
  return t;
}

export function resetDemo() {
  [TOKEN_KEY, ALERT_KEY, COSIGN_KEY].forEach((k) => writeJson(k, null));
  return demoToken();
}

// Value of a shared key, updated when another tab changes it.
export function useShared(key) {
  const [value, setValue] = useState(() => readJson(key));
  useEffect(() => {
    const onStorage = (e) => { if (e.key === key || e.key === null) setValue(readJson(key)); };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [key]);
  return value;
}

export async function api(path, body) {
  const options = body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  };
  const res = await fetch(`${API}${path}`, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Server error ${res.status}`);
  return data;
}

export const SIGNAL_TEXT = {
  unknown_caller: 'caller not in contacts',
  long_call: 'long call',
  code_during_call: 'bank code arrived during the call',
  money_code: 'the code moves money',
  flagged_message: 'a checked message looked like a scam',
  rising_payments: 'rising payments to a new payee',
};
