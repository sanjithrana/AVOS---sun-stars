import { networkInterfaces } from "node:os";
import type { NextConfig } from "next";

/**
 * Next.js dev server blocks cross-origin requests for its dev assets
 * unless the origin is allow-listed. Opening the UI from another device
 * (http://192.168.x.y:3000) then fails to hydrate and pages sit on their
 * loading skeletons. Instead of hardcoding one IP (which breaks when the
 * DHCP lease changes), allow every IPv4 address of this machine.
 */
function localIPv4Addresses(): string[] {
  return Object.values(networkInterfaces())
    .flat()
    .filter((iface): iface is NonNullable<typeof iface> => Boolean(iface) && iface!.family === "IPv4")
    .map((iface) => iface.address);
}

const nextConfig: NextConfig = {
  allowedDevOrigins: ["localhost", "127.0.0.1", ...localIPv4Addresses()],
  // A stray lockfile one level up (e.g. D:\star\package-lock.json) makes
  // Turbopack auto-detect the wrong workspace root, which breaks route
  // resolution (every page 404s). Pin the root to this package explicitly
  // instead of relying on lockfile auto-detection. `next.config.ts` is
  // always loaded from the project root, so process.cwd() is reliable
  // here (and avoids import.meta, which next.config.ts can't use - it's
  // compiled as CommonJS, not ESM).
  turbopack: {
    root: process.cwd(),
  },
  // Animations tab: the Animation Studio service (apps/animation_studio, a Python port of ReelMimic's server)
  // is reached through these same-origin paths, so the browser never makes a cross-site call (the live event
  // stream is the one exception, see components/reelmimic/api.ts). ANIMATION_STUDIO_URL overrides where it runs.
  async rewrites() {
    const target = (process.env.ANIMATION_STUDIO_URL || "http://127.0.0.1:8020").replace(/\/$/, "");
    return [
      { source: "/studio-api/:path*", destination: `${target}/api/:path*` },
      { source: "/studio-files/:path*", destination: `${target}/files/:path*` },
    ];
  },
  experimental: {
    // Reference videos and assets are uploaded through the rewrite above.
    proxyClientMaxBodySize: "2gb",
  },
};

export default nextConfig;
