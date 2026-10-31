import { randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { createVideoServer } from "./video-api.mjs";

const server = createVideoServer();
let nginx;
let analytics;
let affiliation;
process.env.AFFILIATION_WORKER_TOKEN=randomBytes(32).toString("hex");
let stopping = false;
function stop(code) {
  if (stopping) return;
  stopping = true;
  server.close();
  analytics?.kill("SIGTERM");
  affiliation?.kill("SIGTERM");
  nginx?.kill("SIGTERM");
  const deadline = setTimeout(() => { nginx?.kill("SIGKILL"); process.exit(code); }, 5000);
  deadline.unref();
  if (!nginx) process.exit(code);
  else nginx.once("exit", () => process.exit(code));
}
affiliation=spawn(process.execPath,["/app/affiliation-worker.mjs"],{stdio:"inherit"});
// Only the affiliation worker needs the optional Domadoo credentials. They are
// never forwarded to nginx, analytics, the public API or browser subprocesses.
delete process.env.DOMADOO_LOGIN;
delete process.env.DOMADOO_PASSWORD;
affiliation.on("error",()=>stop(1));
affiliation.on("exit",()=>{if(!stopping)stop(1)});
// Content/admin are always available; analytics.enabled controls collection only.
analytics = spawn("python3", ["/app/analytics.py"], { stdio: "inherit" });
analytics.on("error", () => stop(1));
analytics.on("exit", () => { if (!stopping) stop(1); });
server.on("error", () => stop(1));
server.listen(3002, "127.0.0.1", () => {
  nginx = spawn("nginx", ["-g", "daemon off;"], { stdio: "inherit" });
  nginx.on("error", () => stop(1));
  nginx.on("exit", code => { if (!stopping) stop(code || 1); });
});
process.on("SIGTERM", () => stop(0));
process.on("SIGINT", () => stop(0));
