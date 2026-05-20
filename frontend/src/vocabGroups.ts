export const GROUP_FILTER_ALL = "__ALL__";
export const GROUP_FILTER_UNGROUPED = "__UNGROUPED__";

export type VocabGroupOption = {
  value: string;
  label: string;
};

export function toStoredGroupValue(raw: string | null | undefined): string {
  const value = (raw || "").trim();
  return value || GROUP_FILTER_ALL;
}

export function displayGroupName(value: string): string {
  if (value === GROUP_FILTER_UNGROUPED || value === "") {
    return "未分组";
  }
  if (value === GROUP_FILTER_ALL) {
    return "全部";
  }
  return value;
}
