/** 导入数据常带 /.../，展示时去掉外层斜杠再包一层，避免出现 //…// */
export function formatIpaForDisplay(phonetic: string): string {
  const inner = phonetic.trim().replace(/^\/+|\/+$/g, "");
  return inner ? `/${inner}/` : "";
}
