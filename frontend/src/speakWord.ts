/** 浏览器朗读英文单词（不朗读 IPA）；尽量选用系统里音质更好的英语语音（macOS / Windows / Android） */

function normalizedLang(lang: string): string {
  return lang.replace(/_/g, "-").trim();
}

function isEnglishVoice(v: SpeechSynthesisVoice): boolean {
  const l = normalizedLang(v.lang).toLowerCase();
  if (l === "en" || l.startsWith("en-")) {
    return true;
  }
  // 部分机型 / WebView 里 lang 为空，只能靠名称判断是否为英语
  if (!l && /\benglish\b/i.test(v.name)) {
    return true;
  }
  return false;
}

function scoreEnglishVoice(v: SpeechSynthesisVoice): number {
  const name = v.name.toLowerCase();
  const lang = normalizedLang(v.lang).toLowerCase();
  let score = 0;

  if (/^en-us\b/.test(lang)) {
    score += 12;
  } else if (/^en-gb\b/.test(lang)) {
    score += 10;
  } else if (/^en\b/.test(lang) || !lang) {
    score += 5;
  }

  // 离线包略加分；安卓上 Google 远程音常为 false，不能单靠此项排序
  if (v.localService) {
    score += 4;
  }

  // 常见高质量 / 神经网络标识
  if (/\b(neural|premium|enhanced|natural)\b/.test(name)) {
    score += 80;
  }
  // Chrome / Android 常见
  if (/\bgoogle\b/.test(name)) {
    score += 45;
  }
  // Windows Edge / Chrome 在 Windows 上常见的 Microsoft 英语音色
  if (/\bmicrosoft\b/.test(name)) {
    score += 38;
  }
  if (
    /\b(zira|mark|david|hazel|george|susan|sonia|libby|jenny|aria|guy|jason|jane|davis|michelle|christopher|ryan|thomas|ana|emma|andrew|brian|amos|ashley|brandon|clara|elen|ethan|jacob|linda|olivia|paul|steffi|toni|william)\b/.test(
      name
    )
  ) {
    score += 32;
  }
  // 三星等设备自带 TTS
  if (/\bsamsung\b/.test(name)) {
    score += 22;
  }
  // macOS 常见
  if (/\bsamantha\b|\bdaniel\b|\bkaren\b|\bmoira\b|\bfiona\b|\btessa\b|\baaron\b|\btom\b/.test(name)) {
    score += 28;
  }

  // 名称里标明美/英英语，略加分（缓解 lang 异常）
  if (/\benglish\s*\(united states\)\b|\bus english\b/.test(name)) {
    score += 8;
  }
  if (/\benglish\s*\(united kingdom\)\b|\buk english\b|\bbritish\b/.test(name)) {
    score += 6;
  }

  // Apple「紧凑」音色通常偏糊
  if (/\bcompact\b/.test(name)) {
    score -= 70;
  }
  // 老旧低端引擎
  if (/\bpico\b|\bespeak\b/.test(name)) {
    score -= 50;
  }

  return score;
}

function pickBestEnglishVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  let pool = voices.filter(isEnglishVoice);
  if (!pool.length) {
    pool = voices.filter((v) => /\benglish\b/i.test(v.name));
  }
  if (!pool.length) {
    return undefined;
  }
  let best = pool[0];
  let bestScore = scoreEnglishVoice(best);
  for (let i = 1; i < pool.length; i++) {
    const v = pool[i];
    const s = scoreEnglishVoice(v);
    if (s > bestScore) {
      best = v;
      bestScore = s;
    }
  }
  return best;
}

function isAndroidUa(): boolean {
  return typeof navigator !== "undefined" && /Android/i.test(navigator.userAgent);
}

/**
 * 部分安卓 TTS 对单个单词会套「未完成 / 疑问」式升调；补上句号有助于按陈述句收尾。
 */
function utteranceTextForPlatform(text: string): string {
  if (!isAndroidUa()) {
    return text;
  }
  if (/[.!?…]$/.test(text)) {
    return text;
  }
  return `${text}.`;
}

function speakWithSynth(synth: SpeechSynthesis, text: string): void {
  synth.cancel();
  const toSpeak = utteranceTextForPlatform(text);
  const voice = pickBestEnglishVoice(synth.getVoices());
  const u = new SpeechSynthesisUtterance(toSpeak);
  if (voice) {
    u.voice = voice;
    const lang = normalizedLang(voice.lang);
    u.lang = lang || "en-US";
  } else {
    u.lang = "en-US";
  }
  u.rate = 1;
  // 安卓上略压 pitch，减轻句尾上挑感（对 macOS/Windows 保持 1）
  u.pitch = isAndroidUa() ? 0.93 : 1;
  u.volume = 1;
  synth.speak(u);
}

function voiceReadyFallbackMs(): number {
  if (typeof navigator === "undefined") {
    return 700;
  }
  const ua = navigator.userAgent;
  // 安卓上音色列表往往更晚就绪；Windows 偶发也偏慢
  if (/Android/i.test(ua)) {
    return 1400;
  }
  if (/Windows/i.test(ua)) {
    return 900;
  }
  return 650;
}

export function cancelSpeech(): void {
  window.speechSynthesis?.cancel();
}

export function speakEnglishWord(word: string): void {
  const synth = window.speechSynthesis;
  if (!synth) {
    return;
  }
  const text = word.trim();
  if (!text) {
    return;
  }

  const run = () => speakWithSynth(synth, text);

  if (synth.getVoices().length > 0) {
    run();
    return;
  }

  let settled = false;
  const done = () => {
    if (settled) {
      return;
    }
    settled = true;
    synth.removeEventListener("voiceschanged", onVoices);
    window.clearTimeout(fallbackTimer);
    run();
  };

  const onVoices = () => {
    if (synth.getVoices().length > 0) {
      done();
    }
  };

  synth.addEventListener("voiceschanged", onVoices);
  synth.getVoices();
  const fallbackTimer = window.setTimeout(done, voiceReadyFallbackMs());
}
