import { useEffect, useState } from 'react';
import { ALERT_KEY, COSIGN_KEY, api, useShared } from './demo.js';

// Simulated phone of the trusted family member: receives the alert and
// approves or denies the held ATM withdrawal.
export default function Guardian() {
  const alert = useShared(ALERT_KEY);
  const cosign = useShared(COSIGN_KEY);
  const [decided, setDecided] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { setDecided(null); setError(''); }, [cosign?.cosign_id]);

  async function decide(decision) {
    setBusy(true);
    setError('');
    try {
      setDecided(await api(`/v1/cosign/${cosign.cosign_id}/decision`, { decision }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="top">
        <div className="brand">
          <span className="mark" aria-hidden="true" />
          <div>
            <h1>Muragala</h1>
            <p className="tag">Simulated phone · Trusted family member</p>
          </div>
        </div>
      </header>

      <p className="demo">Simulated phone. In a real app this alert arrives as a push notification. Keep this page open.</p>

      <main>
        {!alert && !cosign && (
          <section className="card">
            <h2>අනතුරු ඇඟවීම් නැහැ <span className="small">· No alerts yet</span></h2>
          </section>
        )}

        {alert && (
          <section className="card result high" aria-live="assertive">
            <div className="risk">
              <span className="risk-label">⚠ Muragala</span>
              <span className="risk-score">{alert.score}/10</span>
            </div>
            <p className="big">{alert.message_si}</p>
            <p className="small">
              Your family member has been on a long call with an unknown number, and a bank code arrived during the call.
              Call them now and tell them: do not share the code, end the call.
            </p>
          </section>
        )}

        {cosign && (
          <section className="card result high" aria-live="assertive">
            <h2>ATM එකේ මුදල් ගැනීම නවත්වලා <span className="small">· ATM withdrawal on hold</span></h2>
            <dl className="tx">
              <div><dt>Amount</dt><dd>LKR {Number(cosign.amount).toLocaleString('en-LK')}</dd></div>
              <div><dt>Where</dt><dd>Demo ATM</dd></div>
            </dl>
            {decided ? (
              <p className={decided.status === 'approved' ? 'ok' : 'hold'}>
                {decided.status === 'approved' ? '✓ ඔබ අනුමත කළා · You approved it' : '✗ ඔබ ප්‍රතික්ෂේප කළා · You denied it'}
              </p>
            ) : (
              <>
                <p>ඔබ මේක අනුමත කරනවද? <span className="small">· Do you approve this?</span></p>
                <button className="primary" disabled={busy} onClick={() => decide('deny')}>
                  ප්‍රතික්ෂේප කරන්න <span className="sub">Deny</span>
                </button>
                <button className="ghost" disabled={busy} onClick={() => decide('approve')}>
                  අනුමත කරන්න · Approve
                </button>
              </>
            )}
            {error && <p className="error">{error}</p>}
          </section>
        )}
      </main>

      <footer><a href="/phone">Amma&apos;s phone</a> · <a href="/atm">Demo ATM</a></footer>
    </div>
  );
}
