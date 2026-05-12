import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produce a self-contained Node server in .next/standalone for Docker/Cloud Run.
  output: "standalone",
};

export default nextConfig;
