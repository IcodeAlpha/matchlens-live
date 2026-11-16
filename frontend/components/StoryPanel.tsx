'use client';
import { LANGS } from '../lib/showcase';
import type { Lang, MatchDoc, Style } from '../lib/showcase';

type Props = {
  doc: MatchDoc; now: number; style: Style; lang: Lang; selected: string | null;
  onStyle: (s: Style) => void; onLang: (l: Lang) => void; onSelect: (id: string) => void;
};

const KIND: Record<string, string> = { goal: 'GOAL', red_card: 'RED CARD', big_chance: 'BIG CHANCE' };

export default function StoryPanel({ doc, now, style, lang, selected, onStyle, onLang, onSelect }: Props) {
  const shown = doc.key_moments.filter(m => m.elapsed_seconds <= now);
  const v = doc.verification;
  return (
    <section className="panel story" aria-label="Match story">
      <header className="story-head">
        <div><small>MATCH STORY</small><h2>{doc.label}</h2></div>
        <div className="story-controls">
          <div className="story-toggle" role="group" aria-label="Narration style">
            {(['fan', 'analyst'] as Style[]).map(s => (
              <button key={s} className={style === s ? 'on' : ''} aria-pressed={style === s} onClick={() => onStyle(s)}>
                {s === 'fan' ? 'Fan' : 'Analyst'}
              </button>
            ))}
          </div>
          <label className="story-lang">Language
            <select value={lang} onChange={e => onLang(e.target.value as Lang)}>
              {LANGS.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
          </label>
        </div>
      </header>
      {shown.length === 0
        ? <p className="story-empty">Nothing notable yet. Press play or drag the bar to follow the story.</p>
        : <ol className="story-list">
            {shown.map(m => (
              <li key={m.event_id}>
                <button className={`story-item ${m.kind}${selected === m.event_id ? ' picked' : ''}`}
                        onClick={() => onSelect(m.event_id)}>
                  <span className="story-kind">{KIND[m.kind]}</span>
                  <span className="story-text" lang={lang}>{m.texts[style][lang]}</span>
                  {style === 'analyst' && (
                    <span className="story-evidence">
                      evidence: {m.evidence_event_ids.join(', ')}{m.verified ? ' · verified' : ''}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ol>}
      <footer className="story-foot">
        <b>{v.moments_verified}/{v.moments}</b> narrated moments and <b>{v.snapshots_verified}/{v.snapshots}</b> analysis
        snapshots re-checked against the raw event log. Synthetic data: fictional clubs and players.
        {lang !== 'en' && ' Spanish and Swahili text is template-based and still needs native-speaker review.'}
      </footer>
    </section>
  );
}