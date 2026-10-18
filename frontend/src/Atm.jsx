import { useEffect, useState } from 'react';
import { COSIGN_KEY, SIGNAL_TEXT, TOKEN_KEY, api, demoToken, useShared, writeJson } from './demo.js';

// Mock ATM: asks Muragala before releasing cash, and waits for the trusted
// person when the withdrawal is held.
export default function Atm() {
  const token = useShared(TOKEN_KEY) || demoToken();
  const [amount, setAmount] = useState('200000');
  const [step, setStep] = useState('ready'); // ready | checking | allow | pause | held | approved | denied | expired
  const [res, setRes] = useState(null);
  const [error, setError] = useState('');

  // While held, ask the API for the trusted person's answer every 2 seconds.
  useEffect(() => {
    if (step !== 'held') return undefined;
    const id = setInterval(async () => {
      try {
        const s = await api(`/v1/cosign/${res.cosign_id}`);
        if (s.status !== 'pending') setStep(s.status);
      } catch { /* keep polling */ }
    }, 2000);
    return () => clearInterval(id);
  }, [step, res]);

  async function withdraw() {
    setStep('checking');
    setError('');
    try {
      const r = await api('/v1/cosign/check', { customer_token: token, action: 'atm_withdrawal', amount: Number(amount) });
      setRes(r);
      if (r.decision === 'hold_cosign') {
        writeJson(COSIGN_KEY, { cosign_id: r.cosign_id, amount: r.amount });
        setStep('held');
      } else {
        setStep(r.decision);
      }
    } catch (e) {
      setError(e.message);
      setStep('ready');
    }
  }

  const why = res && res.signals.length > 0 && (
    <p className="small">Muragala risk {res.score}/10: {res.signals.map((s) => SIGNAL_TEXT[s] || s).join(', ')}</p>
  );

  return (
    <div className="page bank">
      <header className="top">
        <div className="brand">
          <span className="mark bankmark" aria-hidden="true" />
          <div>
            <h1>Demo ATM</h1>
            <p className="tag">Mock ATM, not a real bank</p>
          </div>
        </div>
      </header>

      <main>
        {(step === 'ready' || step === 'checking') && (
          <section className="card">
            <h2>මුදල් ගැනීම <span className="small">· Cash withdrawal</span></h2>
            <label className="small" htmlFor="amt">Amount (LKR)</label>
            <input id="amt" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ''))} />
            <button className="primary" disabled={step === 'checking' || !amount} onClick={withdraw}>
              {step === 'checking' ? 'Muragala එකෙන් බලමින්… · Checking…' : 'මුදල් ගන්න · Withdraw'}
            </button>
            {error && <p className="error">{error}</p>}
          </section>
        )}

        {step === 'allow' && (
          <section className="card result low">
            <p className="big ok">✓ මුදල් ගන්න <span className="small">· Please take your cash (demo)</span></p>
          </section>
        )}

        {step === 'pause' && (
          <section className="card result medium">
            <p className="big">ඔබේ ආරක්ෂාවට මේ මුදල් ගැනීම විනාඩි 10ක් නවත්වලා තියෙනවා.</p>
            <p className="small">For your safety this withdrawal is paused for 10 minutes.</p>
            <p>{res.explanation_si}</p>
            {why}
          </section>
        )}

        {step === 'held' && (
          <section className="card result high" aria-live="polite">
            <p className="big">⏸ ඔබේ පවුලේ කෙනාගේ අනුමැතිය එනකම් මුදල් නවත්වලා තියෙනවා.</p>
            <p className="small">Held: waiting for your trusted family member to approve.</p>
            {why}
          </section>
        )}

        {step === 'approved' && (
          <section className="card result low">
            <p className="big ok">✓ අනුමත කළා. මුදල් ගන්න.</p>
            <p className="small">Approved by your family member. Please take your cash (demo).</p>
          </section>
        )}

        {step === 'denied' && (
          <section className="card result high">
            <p className="big hold">✗ ඔබේ පවුලේ කෙනා ප්‍රතික්ෂේප කළා. මුදල් දුන්නේ නැහැ.</p>
            <p>ඔබේ card එකේ පිටුපස ඇති අංකයට බැංකුවට කතා කරන්න.</p>
            <p className="small">Your family member said no. No cash was given. Please call your bank on the number on the back of your card.</p>
          </section>
        )}

        {step === 'expired' && (
          <section className="card result unsure">
            <p className="big">ඉල්ලීම කල් ඉකුත් වුණා.</p>
            <p className="small">The request expired with no answer. Please call your bank.</p>
          </section>
        )}

        {!['ready', 'checking', 'held'].includes(step) && (
          <button className="ghost" onClick={() => { setStep('ready'); setRes(null); }}>New withdrawal</button>
        )}
      </main>

      <footer><a href="/phone">Amma&apos;s phone</a> · <a href="/guardian">Family member&apos;s phone</a></footer>
    </div>
  );
}
