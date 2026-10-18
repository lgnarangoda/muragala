import { useEffect, useState } from 'react';
import { DEMO_MODE } from './api.js';
import { ALERT_KEY, api, demoToken, resetDemo, writeJson } from './demo.js';

const CALLER = '07X XXX XXXX';

function clock(s) {
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

// Simulated phone of the person being scammed (Story 1: a fake CID officer).
export default function Phone() {
  const [token, setToken] = useState(demoToken);
  const [call, setCall] = useState('idle'); // idle | on | ended
  const [seconds, setSeconds] = useState(0);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (call !== 'on') return undefined;
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [call]);

  async function send(body) {
    setBusy(true);
    setError('');
    try {
      return await api('/v1/sessions/events', { device_token: token, ...body });
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function startCall() {
    if (await send({ event: 'call_started', has_guardian: true })) {
      writeJson(ALERT_KEY, null);
      setResult(null);
      setSeconds(0);
      setCall('on');
    }
  }

  async function codeArrives() {
    // The demo skips ahead: the scam call has run for 12 minutes when the code arrives.
    setSeconds(720);
    const r = await send({ event: 'otp_arrived', call_seconds: 720, otp_class: 'bank_transfer' });
    if (r) {
      setResult(r);
      if (r.guardian_alert) writeJson(ALERT_KEY, { message_si: r.guardian_message_si, score: r.score, at: Date.now() });
    }
  }

  async function endCall() {
    if (await send({ event: 'call_ended', call_seconds: seconds })) setCall('ended');
  }

  function newDemo() {
    setToken(resetDemo());
    setCall('idle');
    setSeconds(0);
    setResult(null);
    setError('');
  }

  return (
    <div className="page">
      <header className="top">
        <div className="brand">
          <span className="mark" aria-hidden="true" />
          <div>
            <h1>Muragala</h1>
            <p className="tag">Simulated phone · Amma</p>
          </div>
        </div>
      </header>

      <p className="demo">
        Simulated phone: the buttons stand in for a real call and SMS. Muragala never hears the call. It only
        receives phone facts: an unknown number, the call length, and that a bank code arrived, never the code itself.
      </p>
      {DEMO_MODE && <p className="error">This page needs the live API (set VITE_API_URL).</p>}

      <main>
        {call === 'idle' ? (
          <section className="card">
            <h2>Call එකක් නැහැ <span className="small">· No call</span></h2>
            <button className="primary" disabled={busy} onClick={startCall}>
              නොදන්නා අංකයකින් call එකක්
              <span className="sub">Simulate: an unknown number calls</span>
            </button>
          </section>
        ) : (
          <section className="card">
            <div className="call">
              <p className="small">{call === 'on' ? 'Call එකේ · On call' : 'Call එක ඉවරයි · Call ended'}</p>
              <p className="caller">{CALLER}</p>
              <p className="small">නොදන්නා අංකය · Unknown number · {clock(seconds)}</p>
            </div>
            {call === 'on' && !result && (
              <button className="secondary" disabled={busy} onClick={codeArrives}>
                බැංකු කේතයක් SMS එකෙන් ආවා
                <span className="sub">Simulate: a bank code arrives, 12 minutes into the call</span>
              </button>
            )}
            {call === 'on' && (
              <button className="ghost" disabled={busy} onClick={endCall}>Call එක නවත්වන්න · End call</button>
            )}
          </section>
        )}

        {result && (
          <section className={`card result ${result.risk_level}`} aria-live="assertive">
            <div className="risk">
              <span className="risk-label">නවතින්න! · Stop!</span>
              <span className="risk-score">{result.score}/10</span>
            </div>
            <div className="meter"><span style={{ width: `${result.score * 10}%` }} /></div>
            <p className="big">{result.explanation_si}</p>
            <p className="small">{result.explanation_en}</p>
            {result.guardian_alert && (
              <p className="ok">✓ ඔබේ පවුලේ කෙනාට දැනුම් දුන්නා · Your family member was alerted</p>
            )}
            <a className="secondary" href="/atm" target="_blank" rel="noreferrer">ATM එකට යන්න · Go to the ATM</a>
          </section>
        )}

        {error && <p className="error">{error}</p>}
      </main>

      <footer>
        <p className="small">Demo token: {token} · <button className="link" onClick={newDemo}>Start a new demo</button></p>
        <a href="/guardian" target="_blank" rel="noreferrer">Family member&apos;s phone</a>
        {' · '}<a href="/atm" target="_blank" rel="noreferrer">Demo ATM</a>
        {' · '}<a href="/">Muragala</a>
      </footer>
    </div>
  );
}
