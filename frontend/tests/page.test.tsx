import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Home from '../app/page';

const DATA = path.join(process.cwd(), 'public', 'data');
const read = (rel: string) => JSON.parse(fs.readFileSync(path.join(DATA, rel), 'utf-8'));
const index = read('index.json');
const first = read(index.matches[0].file);

function serveStatic(missing: string[] = []) {
  vi.stubGlobal('fetch', async (url: string) => {
    const rel = String(url).replace(/^.*\/data\//, '');
    const file = path.join(DATA, rel);
    if (missing.includes(rel) || !fs.existsSync(file)) return new Response('not found', { status: 404 });
    return new Response(fs.readFileSync(file, 'utf-8'), { status: 200 });
  });
}
const story = () => screen.findByRole('region', { name: 'Match story' });

beforeEach(() => { window.location.hash = ''; serveStatic(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('MatchLens static replay page', () => {
  it('lists every showcase match and shows real club names, not HOME/AWAY', async () => {
    render(<Home />);
    const picker = await screen.findByLabelText('Choose a showcase match');
    expect(within(picker).getAllByRole('option')).toHaveLength(index.matches.length);
    await story();
    expect(screen.getAllByText(first.teams.home.name).length).toBeGreaterThan(0);
    expect(screen.getAllByText(first.teams.away.name).length).toBeGreaterThan(0);
  });

  it('shows every key moment at full time, plus the verification footer', async () => {
    render(<Home />);
    const panel = await story();
    expect(within(panel).getAllByRole('listitem')).toHaveLength(first.key_moments.length);
    const v = first.verification;
    expect(panel.textContent).toContain(`${v.moments_verified}/${v.moments}`);
    expect(panel.textContent).toContain(`${v.snapshots_verified}/${v.snapshots}`);
  });

  it('switches language and style, using the exported (verified) texts', async () => {
    render(<Home />);
    const panel = await story();
    const m = first.key_moments[0];
    expect(panel.textContent).toContain(m.texts.fan.en);
    fireEvent.change(within(panel).getByLabelText('Language'), { target: { value: 'es' } });
    expect(panel.textContent).toContain(m.texts.fan.es);
    fireEvent.change(within(panel).getByLabelText('Language'), { target: { value: 'sw' } });
    expect(panel.textContent).toContain(m.texts.fan.sw);
    fireEvent.click(within(panel).getByRole('button', { name: 'Analyst' }));
    expect(panel.textContent).toContain(m.texts.analyst.sw);
    expect(panel.textContent).toContain('evidence: ' + m.evidence_event_ids[0]);
  });

  it('only reveals moments the playback clock has reached', async () => {
    render(<Home />);
    const panel = await story();
    const slider = screen.getByLabelText('Match playback minute');
    fireEvent.change(slider, { target: { value: '0' } });
    expect(panel.textContent).toContain('Nothing notable yet');
    const t = first.key_moments[0].elapsed_seconds;
    fireEvent.change(slider, { target: { value: String(t) } });
    const expected = first.key_moments.filter((m: any) => m.elapsed_seconds <= t).length;
    expect(within(panel).getAllByRole('listitem')).toHaveLength(expected);
  });

  it('loads another match from the picker and resets to full time', async () => {
    render(<Home />);
    const picker = await screen.findByLabelText('Choose a showcase match');
    await story();
    const other = index.matches[1];
    fireEvent.change(picker, { target: { value: other.match_id } });
    await waitFor(() => expect(screen.getByRole('region', { name: 'Match story' }).textContent).toContain(other.label));
    expect(window.location.hash).toBe('#' + other.match_id);
  });

  it('opens the match named in the URL hash', async () => {
    window.location.hash = '#' + index.matches[2].match_id;
    render(<Home />);
    const panel = await story();
    expect(panel.textContent).toContain(index.matches[2].label);
  });

  it('shows a clear error when the data files are missing', async () => {
    serveStatic(['index.json']);
    render(<Home />);
    expect(await screen.findByText(/Could not load match data/)).toBeTruthy();
  });
});