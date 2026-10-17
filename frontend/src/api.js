// Talks to Lasitha's Cloud Run backend.
// If VITE_API_URL is empty, the app runs in DEMO MODE with built-in sample answers,
// so the frontend can be built and tested before the backend is deployed.
export const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
export const DEMO_MODE = !API;

export async function checkMessage(text, files) {
  if (DEMO_MODE) return demoCheck(text, files);
  const fd = new FormData();
  fd.append('text', text || '');
  (files || []).forEach((f) => fd.append('files', f));
  // A check takes about 20 s (three Gemini agents); never cut it off before 120 s.
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 120000);
  try {
    const res = await fetch(`${API}/check`, { method: 'POST', body: fd, signal: ctrl.signal });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function getBankSignal(checkId) {
  if (DEMO_MODE) {
    const saved = JSON.parse(sessionStorageGet('demoLast') || 'null');
    if (!saved) return { error: 'no check yet' };
    const score = saved.risk_score;
    return {
      check_id: checkId,
      risk_score: score,
      scam_type: saved.scam_type,
      advisory_refs: saved.citations,
      recommended_action: score >= 70 ? 'hold_and_call_customer' : score >= 40 ? 'show_warning' : 'allow',
    };
  }
  const res = await fetch(`${API}/v1/scam-context-signal/${checkId}`);
  return res.json();
}

function sessionStorageGet(key) {
  try { return sessionStorage.getItem(key); } catch { return null; }
}
function sessionStorageSet(key, value) {
  try { sessionStorage.setItem(key, value); } catch { /* ignore */ }
}

// ---------- DEMO MODE ----------
// Simple keyword rules that imitate the real agent's answer shape.
// Replace by setting VITE_API_URL once the backend is live.
const DEMO_TYPES = [
  {
    type: 'parcel_customs_fee',
    words: ['parcel', 'customs', 'courier', 'deliver', 'pack', 'පාර්සල්', 'රේගු'],
    score: 88,
    cite: ['POL-2026-03-COURIER', 'POST-2026-03-FEE'],
    si: 'මෙය parcel/customs ගාස්තු වංචාවක රටාවයි. තැපෑල, රේගුව හෝ courier ආයතන SMS link එකකින් ගාස්තු ඉල්ලන්නේ නැහැ.',
    en: 'This matches the parcel/customs fee scam pattern. Post, Customs and couriers do not ask for fees through SMS links.',
  },
  {
    type: 'fake_investment_pyramid',
    words: ['invest', 'profit', 'ලාභ', 'ආයෝජන', 'guarantee', 'telegram group', 'bonus', 'trading'],
    score: 92,
    cite: ['CBSL-BSP-PYRAMID', 'POL-2026-01-INVEST'],
    si: 'මෙය ව්‍යාජ ආයෝජන / pyramid වංචාවක රටාවයි. සහතික කළ ලාභ සහ යාළුවන් එකතු කිරීමට bonus දීම CBSL අනතුරු අඟවන ලක්ෂණ.',
    en: 'This matches a fake investment / pyramid scheme. Guaranteed profits and bonuses for recruiting are CBSL warning signs.',
  },
  {
    type: 'job_task',
    words: ['job', 'like', 'task', 'registration fee', 'part time', 'commission', 'රැකියා'],
    score: 85,
    cite: ['POL-2026-01-JOB'],
    si: 'මෙය ව්‍යාජ online රැකියා / task වංචාවක රටාවයි. සැබෑ සේවා යෝජකයෙක් වැඩ පටන් ගන්න ගාස්තු ඉල්ලන්නේ නැහැ.',
    en: 'This matches a fake online job / task scam. Real employers do not charge you to start work.',
  },
  {
    type: 'impersonation_official',
    words: ['cid', 'police', 'arrest', 'පොලිස්', 'fine', 'court'],
    score: 90,
    cite: ['POL-2026-07-IMPERSONATION'],
    si: 'මෙය නිලධාරියෙකු ලෙස පෙනී සිටින වංචාවක රටාවයි. Police, CID හෝ CBSL WhatsApp හරහා මුදල් ඉල්ලන්නේ නැහැ.',
    en: 'This matches an official-impersonation scam. Police, CID and CBSL never ask for money on WhatsApp.',
  },
  {
    type: 'otp_account_takeover',
    words: ['otp', 'pin', 'password', '.apk', 'card eka block', 'unblock'],
    score: 95,
    cite: ['POL-2026-01-PHISHING', 'POL-2026-04-APK'],
    si: 'මෙය OTP / ගිණුම් පැහැරගැනීමේ වංචාවක රටාවයි. OTP, PIN හෝ password කාටවත් දෙන්න එපා.',
    en: 'This matches an OTP / account takeover scam. Never share your OTP, PIN or password.',
  },
];

async function demoCheck(text, files) {
  await new Promise((r) => setTimeout(r, 1200));
  const t = (text || '').toLowerCase();
  const legit = /debited|electricity bill|විදුලි බිල|bus ekata/.test(t);
  let hit = DEMO_TYPES.find((d) => d.words.some((w) => t.includes(w)));
  if (!hit && files && files.length && !t) {
    hit = DEMO_TYPES[0]; // screenshot only: demo answer
  }
  let result;
  if (legit || !hit) {
    result = {
      risk_score: legit ? 8 : 35,
      risk_level: legit ? 'low' : 'unsure',
      scam_type: legit ? 'not_scam' : 'unsure',
      explanation_si: legit
        ? 'මෙහි සාමාන්‍ය වංචා ලක්ෂණ පෙනෙන්නේ නැහැ. ඒ වුණත් link එකක් click කරන්න කලින් නිල app එකෙන් තහවුරු කරගන්න.'
        : 'අපට විශ්වාසයෙන් කියන්න බැහැ. ගෙවන්න කලින් පවුලේ කෙනෙක්ගෙන් හෝ බැංකුවෙන් අහන්න.',
      explanation_en: legit
        ? 'No common scam signs found. Still, confirm through the official app before clicking any link.'
        : "We can't be sure. Ask a family member or your bank before paying.",
      actions_si: ['ඔබේ බැංකුවේ card එකේ පිටුපස ඇති අංකයට අමතන්න', 'Message එකේ ඇති අංකවලට අමතන්න එපා'],
      actions_en: ['Call the number on the back of your bank card', 'Do not call numbers given in the message'],
      citations: legit ? [] : ['CBSL-BSP-PROTECT'],
      analysis: { scam_type: legit ? 'not_scam' : 'unsure', risk_score: legit ? 8 : 35, tool_findings: { demo_mode: true } },
    };
  } else {
    result = {
      risk_score: hit.score,
      risk_level: 'high',
      scam_type: hit.type,
      explanation_si: hit.si,
      explanation_en: hit.en,
      actions_si: [
        'තවම ගෙවන්න එපා.',
        'Message එකේ ඇති link එක හෝ අංකය භාවිතා කරන්න එපා.',
        'ඔබේ බැංකුවේ card එකේ පිටුපස ඇති අංකයට අමතා තහවුරු කරන්න.',
        'මුදල් යැව්වා නම් වහාම බැංකුවට සහ CERT hotline 101 ට දන්වන්න.',
      ],
      actions_en: [
        "Don't pay yet.",
        "Don't use the link or number in the message.",
        'Call the number on the back of your bank card to check.',
        'If you already sent money, tell your bank and CERT hotline 101 right away.',
      ],
      citations: hit.cite,
      guardian_message_si:
        `Muragala අනතුරු ඇඟවීම: ඔබේ පවුලේ කෙනෙකුට ලැබුණු message එකක් ${hit.type} වංචා රටාවට ගැළපෙනවා (අවදානම ${hit.score}/100). ` +
        'කරුණාකර දැන්ම කතා කරලා කියන්න: "ගෙවන්න එපා, මුලින් බැංකුවට කතා කරමු."',
      analysis: {
        scam_type: hit.type,
        risk_score: hit.score,
        tool_findings: { demo_mode: true, rule_signals: ['urgency', 'payment_request'], web_risk: 'not checked in demo' },
      },
    };
  }
  result.check_id = `demo-${Date.now()}`;
  sessionStorageSet('demoLast', JSON.stringify(result));
  return result;
}
