/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/research",
        destination: "https://ai-company-researcher-production.up.railway.app/research",
      },
    ];
  },
};
module.exports = nextConfig;
