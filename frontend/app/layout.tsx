import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'MatchLens Live | Broadcast Studio', description: 'Evidence-linked synthetic football match intelligence' };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}</body></html>; }
