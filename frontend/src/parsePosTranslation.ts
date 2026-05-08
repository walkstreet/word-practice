export type PosTranslationRow = { pos: string; meaning: string };

export type VocabSense = { part_of_speech: string; meaning: string };

export function resolvePosTranslationRows(
  senses: VocabSense[] | null | undefined,
  partOfSpeech: string,
  translation: string
): PosTranslationRow[] {
  if (senses && senses.length > 0) {
    return senses.map((s) => ({
      pos: (s.part_of_speech || "").trim() || "词性待补充",
      meaning: (s.meaning || "").trim() || "释义待补充"
    }));
  }
  return parsePosTranslationRows(partOfSpeech, translation);
}

export function parsePosTranslationRows(partOfSpeech: string, translation: string): PosTranslationRow[] {
  const normalizePosLabel = (raw: string) =>
    raw
      .replace(/(名词|动词|形容词|副词|介词|代词|连词|感叹词|数词|冠词)/g, "")
      .replace(/\s+/g, " ")
      .trim();

  const normalizedTranslation = translation.trim();
  const posBlockPattern =
    /((?:名词|动词|形容词|副词|介词|代词|连词|感叹词|数词|冠词)?\s*(?:n\.|v\.|vt\.|vi\.|adj\.|adv\.|prep\.|pron\.|conj\.|int\.|num\.|art\.))/gi;
  const matches = Array.from(normalizedTranslation.matchAll(posBlockPattern));

  if (matches.length >= 2) {
    return matches.map((match, index) => {
      const start = match.index ?? 0;
      const nextStart = matches[index + 1]?.index ?? normalizedTranslation.length;
      const label = normalizePosLabel(match[1]);
      const meaning = normalizedTranslation
        .slice(start + match[0].length, nextStart)
        .replace(/^[；;\s]+/, "")
        .replace(/[；;\s]+$/, "")
        .trim();
      return {
        pos: label || "词性待补充",
        meaning: meaning || "释义待补充"
      };
    });
  }

  const posItems = partOfSpeech
    .split(/[;；|/]/)
    .map((item) => normalizePosLabel(item))
    .filter(Boolean);
  if (posItems.length > 1) {
    return posItems.map((pos, index) => ({
      pos,
      meaning: index === 0 ? normalizedTranslation || "释义待补充" : "释义待补充"
    }));
  }

  return [
    {
      pos: normalizePosLabel(partOfSpeech) || "词性待补充",
      meaning: normalizedTranslation || "释义待补充"
    }
  ];
}
