/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required by docker/dashboard.Dockerfile (copies .next/standalone).
  output: "standalone",
};

export default nextConfig;
