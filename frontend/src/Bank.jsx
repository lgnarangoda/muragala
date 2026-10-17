import { useState } from 'react';
import { getBankSignal } from './api.js';

function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

// Mock bank app: shows Muragala inside the payment flow.
export default function Bank() {
  const [step, setStep] = useState('form');
  const [onCall, setOnCall] = useState(false);
  const [signal, setSignal] = useState(null);
  const [note, setNote] = useState('');

  async function loadSignal() {
    const id = storageGet('lastCheckId');
    if (!id) {
      setNote('No Muragala check found yet. Check the chat first, then come back.');
      return;
    }
    setSignal(await getBankSignal(id));
    setStep('signal');
  }

  return (
    <div className="page bank">
      <header className="top">
        <div className="brand">
          <span className="mark bankmark" aria-hidden="true" />
          <div>
            <h1>Demo Bank</h1>
            <p className="tag">Transfer funds</p>
          </div>
        </div>
      </header>

      <main>
        {step === 'form' && (
          <section className="card">
            <dl className="tx">
              <div><dt>Payee</dt><dd>New payee · 1002xxxxxx</dd></div>
              <div><dt>Amount</dt><dd>LKR 50,000.00</dd></div>
            </dl>
            <label className="check">
              <input type="checkbox" checked={onCall} onChange={(e) => setOnCall(e.target.checked)} />
              <span>Simulate: I'm on a phone call right now</span>
            </label>
            <button className="primary" onClick={() => setStep('ask')}>Pay</button>
          </section>
        )}

        {step === 'ask' && (
          <section className="card">
            {onCall && (
              <p className="warn">⚠ ඔබ දැන් call එකක ඉන්නවා. Call එකේ කෙනෙක් ගෙවන්න කියනවා නම් මොහොතක් නවතින්න.</p>
            )}
            <h2>මේ ගෙවීම chat එකක හෝ call එකක කවුරුහරි ඉල්ලපු එකක්ද?</h2>
            <p className="small">Is someone in a chat or call asking you to make this payment?</p>
            <a className="primary" href="/" target="_blank" rel="noreferrer">ඔව් — chat එක Muragala එකෙන් check කරන්න</a>
            <button className="secondary" onClick={loadSignal}>Check කළා, ඉදිරියට යන්න</button>
            <button className="ghost" onClick={() => setStep('done')}>නැහැ, ගෙවන්න</button>
            {note && <p className="error">{note}</p>}
          </section>
        )}

        {step === 'signal' && signal && (
          <section className="card">
            <h2>Bank received Muragala's scam-context signal</h2>
            <pre className="json">{JSON.stringify(signal, null, 2)}</pre>
            {signal.recommended_action === 'hold_and_call_customer' ? (
              <p className="hold"><b>Payment on hold.</b> Our fraud team will call you on your registered number.</p>
            ) : (
              <button className="primary" onClick={() => setStep('done')}>Continue payment</button>
            )}
          </section>
        )}

        {step === 'done' && (
          <section className="card"><p>Payment sent (demo).</p></section>
        )}
      </main>

      <footer><a href="/">Back to Muragala</a></footer>
    </div>
  );
}
