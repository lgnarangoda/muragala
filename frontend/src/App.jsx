import { useEffect, useState } from 'react';
import { checkMessage, DEMO_MODE } from './api.js';

const SAMPLES = [
  { label: 'Parcel scam (Singlish)', text: 'Sir oyage parcel eka customs eke. Rs 4,500 ewanna me link eken ada ma. http://example.com/pay' },
  { label: 'Investment scam (සිංහල)', text: 'දිනකට 5% ලාභ සහතිකයි! අදම රු. 25,000 ආයෝජනය කරලා අපේ Telegram group එකට join වෙන්න. කාටවත් කියන්න එපා.' },
  { label: 'Job scam (English)', text: 'Earn LKR 10,000 daily by liking videos. Pay a LKR 2,000 registration fee today to start.' },
  { label: 'Real bank SMS (legit)', text: 'Your account was debited LKR 1,250.00 at a supermarket. If this was not you, call the number on the back of your card.' },
];

const LEVEL_TEXT = {
  high: { si: 'ඉහළ අවදානම', en: 'High risk', ta: 'அதிக ஆபத்து' },
  medium: { si: 'මධ්‍යම අවදානම', en: 'Medium risk', ta: 'நடுத்தர ஆபத்து' },
  low: { si: 'අඩු අවදානම', en: 'Low risk', ta: 'குறைந்த ஆபத்து' },
  unsure: { si: 'විශ්වාස නැහැ', en: 'Not sure', ta: 'உறுதியாகத் தெரியவில்லை' },
};

// Answers come in all three languages; UI labels without a Tamil string fall back to English.
const LANGS = [['si', 'සිංහල'], ['en', 'English'], ['ta', 'தமிழ்']];

function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch { /* ignore */ }
}

export default function App() {
  const [text, setText] = useState('');
  const [files, setFiles] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0);

  // The real check takes ~20 s, so show what is happening instead of a frozen button.
  useEffect(() => {
    if (!loading) { setStep(0); return undefined; }
    const id = setInterval(() => setStep((n) => Math.min(n + 1, 2)), 7000);
    return () => clearInterval(id);
  }, [loading]);
  const [error, setError] = useState('');
  const [lang, setLang] = useState('si');
  const [guardian, setGuardian] = useState(storageGet('guardian') || '');

  // Load anything shared from the Android share sheet.
  useEffect(() => {
    if (!new URLSearchParams(location.search).get('shared')) return;
    if (!('caches' in window)) return;
    caches.open('shared').then(async (cache) => {
      const res = await cache.match('/shared-form');
      if (!res) return;
      const form = await res.formData();
      setText([form.get('title'), form.get('text'), form.get('url')].filter(Boolean).join(' '));
      setFiles(form.getAll('media').filter((f) => f && f.size));
      await cache.delete('/shared-form');
      history.replaceState(null, '', '/');
    });
  }, []);

  async function check() {
    if (!text.trim() && files.length === 0) {
      setError(lang === 'si' ? 'මුලින් message එකක් paste කරන්න හෝ screenshot එකක් දාන්න.' : 'Paste a message or add a screenshot first.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await checkMessage(text, files);
      storageSet('lastCheckId', data.check_id);
      setResult(data);
    } catch (e) {
      setError(lang === 'si' ? 'පරීක්ෂා කරන්න බැරි වුණා. නැවත උත්සාහ කරන්න.' : "Couldn't check right now. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const level = result ? result.risk_level || (result.risk_score >= 70 ? 'high' : result.risk_score >= 40 ? 'medium' : 'low') : null;
  const waLink = result && guardian && result.guardian_message_si
    ? `https://wa.me/${guardian.replace(/\D/g, '')}?text=${encodeURIComponent(result.guardian_message_si)}`
    : null;
  const t = (si, en, ta) => (lang === 'si' ? si : lang === 'ta' && ta ? ta : en);

  return (
    <div className="page">
      <header className="top">
        <div className="brand">
          <span className="mark" aria-hidden="true" />
          <div>
            <h1>Muragala</h1>
            <p className="tag">{t('ගෙවන්න කලින් අහන්න', 'Check before you pay')}</p>
          </div>
        </div>
        <div className="langs">
          {LANGS.map(([code, label]) => (
            <button key={code} className="ghost" aria-pressed={lang === code} onClick={() => setLang(code)}>{label}</button>
          ))}
        </div>
      </header>

      {DEMO_MODE && (
        <p className="demo">{t('Demo mode: backend එක සම්බන්ධ කරලා නැහැ. පිළිතුරු sample ඒවා.', 'Demo mode: no backend connected, answers are samples.')}</p>
      )}

      <main>
        <section className="card">
          <h2>{t('සැක හිතෙන message එක මෙතනට දාන්න', 'Add the suspicious message')}</h2>
          <div className="samples">
            <span className="small">{t('උදාහරණයක් try කරන්න:', 'Try a sample:')}</span>
            {SAMPLES.map((s) => (
              <button key={s.label} className="chip" onClick={() => { setText(s.text); setFiles([]); setResult(null); }}>
                {s.label}
              </button>
            ))}
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            placeholder={t('WhatsApp / SMS message එක මෙතන paste කරන්න', 'Paste the WhatsApp / SMS message here')}
          />
          <label className="file">
            <input type="file" accept="image/*,audio/*" multiple onChange={(e) => setFiles([...e.target.files])} />
            <span>{t('Screenshot හෝ voice note එකක් එකතු කරන්න', 'Add a screenshot or voice note')}</span>
          </label>
          {files.length > 0 && (
            <p className="small">{files.length} {t('file එකතු කළා', 'file(s) added')} · <button className="link" onClick={() => setFiles([])}>{t('ඉවත් කරන්න', 'remove')}</button></p>
          )}
          <button className="primary" onClick={check} disabled={loading}>
            {loading ? t('බලමින්…', 'Checking…') : t('Check කරන්න', 'Check')}
          </button>
          {loading && (
            <p className="small" aria-live="polite">
              {[
                t('1/3 · Message එක කියවමින්…', '1/3 · Reading the message…'),
                t('2/3 · CBSL, Police, CERT advisories එක්ක සසඳමින්…', '2/3 · Comparing with CBSL, Police and CERT advisories…'),
                t('3/3 · සිංහල උත්තරේ ලියමින්…', '3/3 · Writing the answer…'),
              ][step]}
              {' '}{t('(තත්පර 20ක් විතර)', '(about 20 seconds)')}
            </p>
          )}
          {error && <p className="error">{error}</p>}
        </section>

        {result && (
          <section className={`card result ${level}`} aria-live="polite">
            <div className="risk">
              <span className="risk-label">{LEVEL_TEXT[level] ? LEVEL_TEXT[level][lang] : level}</span>
              <span className="risk-score">{result.risk_score}/100</span>
            </div>
            <div className="meter"><span style={{ width: `${Math.min(100, Math.max(0, result.risk_score))}%` }} /></div>

            <p className="explain">{result[`explanation_${lang}`] || result.explanation_en}</p>

            <h3>{t('දැන් කරන්න ඕනේ දේ', 'What to do now', 'இப்போது செய்ய வேண்டியவை')}</h3>
            <ol className="actions">
              {(result[`actions_${lang}`] || result.actions_en || result.actions_si || []).map((a, i) => <li key={i}>{a}</li>)}
            </ol>

            <p className="small">{t('මූලාශ්‍ර', 'Sources', 'ஆதாரங்கள்')}: {(result.citations || []).join(', ') || t('නැත', 'none', 'இல்லை')}</p>

            {result.guardian_message_si && (
              waLink ? (
                <a className="primary wa" href={waLink} target="_blank" rel="noreferrer">
                  {t('පවුලේ කෙනාට දැනුම් දෙන්න (WhatsApp)', 'Alert my family (WhatsApp)')}
                </a>
              ) : (
                <p className="small">{t('පවුලේ කෙනාට දැනුම් දෙන්න පහළ Guardian සැකසුම් වල අංකයක් දාන්න.', 'Add a family number in Guardian settings below to alert them.')}</p>
              )
            )}

            <details className="how">
              <summary>{t('Muragala තීරණය කළේ කොහොමද', 'How Muragala decided')}</summary>
              <ol>
                <li><b>Intake agent:</b> {t('message එක කියවලා links, මුදල් සහ නම් වෙන් කළා', 'read the message and pulled out links, amounts and names')}</li>
                <li><b>Analysis agent:</b> {t('වර්ගය', 'type')} <b>{result.analysis?.scam_type || result.scam_type}</b>, {t('අවදානම', 'risk')} {result.analysis?.risk_score ?? result.risk_score}/100</li>
                <li><b>Tools:</b><pre>{JSON.stringify(result.analysis?.tool_findings ?? {}, null, 2)}</pre></li>
                <li><b>Action agent:</b> {t('උපදෙස් පදනම් කළේ', 'advice grounded in')} {(result.citations || []).join(', ') || t('ගැළපෙන advisory එකක් නැහැ', 'no matching advisory')}</li>
              </ol>
            </details>

            <p className="disclaimer">{t('මෙය AI තක්සේරුවකි, සහතිකයක් නොවේ. සැකයක් ඇත්නම් ඔබේ බැංකුවට කතා කරන්න.', 'This is an AI assessment, not a guarantee. If in doubt, call your bank.', 'இது AI மதிப்பீடு மட்டுமே, உத்தரவாதம் அல்ல. சந்தேகம் இருந்தால் உங்கள் வங்கியை அழைக்கவும்.')}</p>
          </section>
        )}

        <details className="card settings">
          <summary>{t('Guardian සැකසුම්', 'Guardian settings')}</summary>
          <label className="small" htmlFor="g">{t('පවුලේ කෙනෙකුගේ WhatsApp අංකය (උදා: 9477xxxxxxx)', "A family member's WhatsApp number (e.g. 9477xxxxxxx)")}</label>
          <input
            id="g"
            inputMode="tel"
            value={guardian}
            placeholder="9477xxxxxxx"
            onChange={(e) => { setGuardian(e.target.value); storageSet('guardian', e.target.value); }}
          />
          <p className="small">{t('අංකය save වෙන්නේ ඔබේ phone එකේ විතරයි. Message එක යවන්නේ ඔබ button එක tap කළාම විතරයි.', 'The number is saved only on your phone. A message is sent only when you tap the button.')}</p>
        </details>
      </main>

      <footer>
        <a href="/bank">{t('Demo bank එක බලන්න', 'Open the demo bank')}</a>
        {' · '}<a href="/phone">Coercion Shield demo</a>
      </footer>
    </div>
  );
}
