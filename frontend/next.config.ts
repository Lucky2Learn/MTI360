import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Do not advertise the framework in response headers.
  poweredByHeader: false,
  // T00-03 adds `output: "standalone"` for the Docker image.
};

export default nextConfig;
