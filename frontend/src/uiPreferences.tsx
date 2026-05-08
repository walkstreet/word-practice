import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

type UiPreferences = {
  showPhonetic: boolean;
  toggleShowPhonetic: () => void;
};

// v3: 默认关；v2 首屏会立即写入 "1"，与「默认关」冲突，故换 key
const STORAGE_KEY = "showPhonetic_v3";

const UiPreferencesContext = createContext<UiPreferences | null>(null);

function readStoredPhoneticPreference(): boolean {
  const v = localStorage.getItem(STORAGE_KEY);
  // 默认隐藏音标；仅当用户明确开过（存为 "1"）才展示
  if (v === null || v === "") {
    return false;
  }
  return v === "1";
}

export function UiPreferencesProvider({ children }: { children: ReactNode }) {
  const [showPhonetic, setShowPhonetic] = useState<boolean>(() => readStoredPhoneticPreference());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, showPhonetic ? "1" : "0");
  }, [showPhonetic]);

  const value = useMemo(
    () => ({
      showPhonetic,
      toggleShowPhonetic: () => setShowPhonetic((prev) => !prev)
    }),
    [showPhonetic]
  );

  return <UiPreferencesContext.Provider value={value}>{children}</UiPreferencesContext.Provider>;
}

export function useUiPreferences() {
  const context = useContext(UiPreferencesContext);
  if (!context) {
    throw new Error("useUiPreferences must be used within UiPreferencesProvider");
  }
  return context;
}
