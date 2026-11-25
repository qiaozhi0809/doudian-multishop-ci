import { useCallback, useEffect, useState } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';
export const THEME_KEY = 'doudian.theme';

const isPref = (v: unknown): v is ThemePreference => v === 'light' || v === 'dark' || v === 'system';

export function readTheme(): ThemePreference {
  try {
    const v = window.localStorage.getItem(THEME_KEY);
    if (isPref(v)) return v;
  } catch {
    /* 存储不可用时用默认 */
  }
  // 默认浅色：深色模式还没在 Windows 真机上逐页验过，先让用户自己选
  return 'light';
}

const systemQuery = () => (typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-color-scheme: dark)') : null);

export function resolveTheme(pref: ThemePreference): 'light' | 'dark' {
  if (pref === 'system') return systemQuery()?.matches ? 'dark' : 'light';
  return pref;
}

export function applyTheme(pref: ThemePreference) {
  document.documentElement.dataset.theme = resolveTheme(pref);
}

export function saveTheme(pref: ThemePreference) {
  try {
    window.localStorage.setItem(THEME_KEY, pref);
  } catch {
    /* 记不住也不影响本次使用 */
  }
  applyTheme(pref);
  window.dispatchEvent(new CustomEvent('doudian.theme-change', { detail: pref }));
}

/** 启动时尽早调用：应用已存的偏好，并在「跟随系统」时监听系统切换。 */
export function initTheme() {
  applyTheme(readTheme());
  systemQuery()?.addEventListener?.('change', () => {
    if (readTheme() === 'system') applyTheme('system');
  });
}

/** 头像菜单、设置页共用：偏好与设置函数，多处同时用也保持同步。 */
export function useTheme(): [ThemePreference, (pref: ThemePreference) => void] {
  const [pref, setPref] = useState<ThemePreference>(readTheme);
  useEffect(() => {
    const sync = () => setPref(readTheme());
    window.addEventListener('doudian.theme-change', sync);
    return () => window.removeEventListener('doudian.theme-change', sync);
  }, []);
  const set = useCallback((next: ThemePreference) => {
    saveTheme(next);
    setPref(next);
  }, []);
  return [pref, set];
}
