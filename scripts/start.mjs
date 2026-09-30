import { spawn } from "node:child_process";
import { createVideoServer } from "./video-api.mjs";

const server = createVideoServer();
let nginx;
let analytics;
let stopping = false;
function stop(code) {
  if (stopping) return;
  stopping = true;
  server.close();
  analytics?.kill("SIGTERM");
  nginx?.kill("SIGTERM");
  const deadline = setTimeout(() => { nginx?.kill("SIGKILL"); process.exit(code); }, 5000);
  deadline.unref();
  if (!nginx) process.exit(code);
  else nginx.once("exit", () => process.exit(code));
}
// STATS_PASSWORD is retained only as a legacy enable flag; VPN controls access.
const analyticsEnabled = process.env.ANALYTICS_ENABLED ?? (process.env.STATS_PASSWORD ? "true" : "false");
if (analyticsEnabled === "true") {
  analytics = spawn("python3", ["/app/analytics.py"], { stdio: "inherit" });
  analytics.on("error", () => stop(1));
  analytics.on("exit", () => { if (!stopping) stop(1); });
}
server.on("error", () => stop(1));
server.listen(3002, "127.0.0.1", () => {
  nginx = spawn("nginx", ["-g", "daemon off;"], { stdio: "inherit" });
  nginx.on("error", () => stop(1));
  nginx.on("exit", code => { if (!stopping) { analytics?.kill("SIGTERM"); server.close(); process.exit(code || 1); } });
});
process.on("SIGTERM", () => stop(0));
process.on("SIGINT", () => stop(0));
