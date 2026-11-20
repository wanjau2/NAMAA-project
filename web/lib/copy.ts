/**
 * Chrome (navigation / session) copy.
 *
 * Clinical explanations, rule outcomes and source-note text stay in English
 * until Alfred supplies reviewed wording. Arabic strings in this file are
 * unreviewed demonstration translations: they must keep that label, and a
 * direction change alone is not a completed translation (Q2).
 */

export const LANGUAGE_SCOPE = {
  recorded: "2026-11-20",
  clinicalCopy: "en" as const,
  arabicChrome: "unreviewed_demo" as const,
  rtlMechanics: true,
} as const;

export type ChromeKey =
  | "worklist"
  | "population"
  | "currentPage"
  | "simulatedRole"
  | "language"
  | "resetDemo"
  | "resetConfirm"
  | "resetConfirmAction"
  | "cancel"
  | "unreviewedTranslation"
  | "session"
  | "backToWorklist"
  | "backToCase"
  | "caseOverview"
  | "caseSections"
  | "reviewSource"
  | "retrievedContext"
  | "inspectorTitle";

const EN: Record<ChromeKey, string> = {
  worklist: "Worklist",
  population: "Population view",
  currentPage: "Current page",
  simulatedRole: "Simulated role",
  language: "Language",
  resetDemo: "Reset demo",
  resetConfirm: "Retires this synthetic workspace and starts a new one.",
  resetConfirmAction: "Reset session",
  cancel: "Cancel",
  unreviewedTranslation: "Unreviewed demo translation",
  session: "Session",
  backToWorklist: "Back to worklist",
  backToCase: "Back to case detail",
  caseOverview: "Case overview",
  caseSections: "Case sections",
  reviewSource: "Review source facts",
  retrievedContext: "Retrieved context",
  inspectorTitle: "Identifiers, audit and outbox",
};

/** Unreviewed demonstration translations. Never present as clinically approved. */
const AR: Record<ChromeKey, string> = {
  worklist: "قائمة العمل",
  population: "عرض السكان",
  currentPage: "الصفحة الحالية",
  simulatedRole: "الدور المحاكى",
  language: "اللغة",
  resetDemo: "إعادة تعيين العرض",
  resetConfirm: "يُنهي مساحة العمل التركيبية هذه ويبدأ مساحة جديدة.",
  resetConfirmAction: "إعادة تعيين الجلسة",
  cancel: "إلغاء",
  unreviewedTranslation: "ترجمة تجريبية غير مراجعة",
  session: "الجلسة",
  backToWorklist: "العودة إلى قائمة العمل",
  backToCase: "العودة إلى تفاصيل الحالة",
  caseOverview: "نظرة عامة على الحالة",
  caseSections: "أقسام الحالة",
  reviewSource: "مراجعة الحقائق المصدرية",
  retrievedContext: "السياق المسترجع",
  inspectorTitle: "المعرّفات والتدقيق وصندوق الصادر",
};

export function chrome(locale: "en" | "ar", key: ChromeKey): string {
  return locale === "ar" ? AR[key] : EN[key];
}
