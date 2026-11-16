import type { MatchEvent, Tactical } from './types';

// Static showcase data written by backend/scripts/export_showcase.py into public/data.
// Set NEXT_PUBLIC_BASE_PATH at build time when the site is served from a sub-path.
export const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? '';

export type Lang = 'en' | 'es' | 'sw';
export type Style = 'fan' | 'analyst';
export const LANGS: { code: Lang; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Español' },
  { code: 'sw', label: 'Kiswahili' },
];

export type Moment = {
  event_id: string; elapsed_seconds: number; kind: 'goal' | 'red_card' | 'big_chance';
  team_id: 'home' | 'away' | null; player_id: string | null; xg: number | null;
  score_home: number; score_away: number; evidence_event_ids: string[]; verified: boolean;
  texts: Record<Style, Record<Lang, string>>;
};
export type Squad = {
  side: 'home' | 'away'; name: string; short: string; color: string;
  players: { number: number; player_id: string; name: string; position: string }[];
};
export type Verification = {
  moments: number; moments_verified: number; snapshots: number; snapshots_verified: number; method: string;
};
export type Snapshot = { as_of_seconds: number; analysis: Tactical };
export type MatchDoc = {
  match_id: string; seed: number; label: string; teams: { home: Squad; away: Squad };
  key_moments: Moment[]; verification: Verification; events: MatchEvent[];
  snapshots: Snapshot[]; snapshot_step_seconds: number;
};
export type Club = { name: string; short: string; color: string };
export type IndexEntry = {
  match_id: string; seed: number; label: string; file: string; tags: string[];
  final_score: { home: number; away: number }; home: Club; away: Club;
};
export type IndexFile = { synthetic: true; matches: IndexEntry[] };

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/data/${path}`);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}
export const loadIndex = () => getJson<IndexFile>('index.json');
export const loadMatch = (file: string) => getJson<MatchDoc>(file);

/** Latest analysis snapshot at or before the playback clock (binary search); null before the first. */
export function pickSnapshot(snaps: Snapshot[], now: number): Tactical | null {
  let lo = 0, hi = snaps.length - 1, best = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (snaps[mid].as_of_seconds <= now) { best = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return best < 0 ? null : snaps[best].analysis;
}