import type { NextConfig } from 'next';

// Static export: `npm run build` writes a plain-HTML site to ./out that any free
// static host can serve. No server, no backend, no API keys.
// For a GitHub Pages project site set NEXT_PUBLIC_BASE_PATH=/your-repo-name at build time.
const nextConfig: NextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || undefined,
};
export default nextConfig;