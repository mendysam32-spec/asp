import { DurableObject } from "cloudflare:workers";

/**
 * ASP (Agent SP) — Flask dashboard runs INSIDE a Cloudflare Container.
 * The Worker below is a tiny router: every request goes to ONE stateful
 * container instance ("asp-singleton") because the Flask app keeps state
 * in local JSON files (data/*.json). Load-balancing across instances
 * would split that state, so we pin to a single DO.
 *
 * Container listens on 0.0.0.0:5001 (see Dockerfile + run_background.py).
 * Health endpoint already exists in Flask: GET /api/health.
 */

const CONTAINER_PORT = 5001;
const INACTIVITY_TIMEOUT_MS = 10 * 60 * 1000; // sleep after 10m idle
const SINGLETON_NAME = "asp-singleton";

// Every env var the Flask app may read. Non-secret defaults come from
// wrangler.jsonc `vars`; secrets come from `wrangler secret put` / bulk.
// Only defined values are forwarded so empty strings never wipe container env.
const FORWARDED_VARS = [
  "PORT",
  "PYTHONUNBUFFERED",
  "NVIDIA_API_KEY",
  "NVIDIA_MODEL",
  "OPENROUTER_API_KEY",
  "OPENROUTER_MODEL",
  "OPENROUTER_REFERER",
  "OPENROUTER_TITLE",
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "TIKTOK_CLIENT_KEY",
  "TIKTOK_CLIENT_SECRET",
  "TIKTOK_ACCESS_TOKEN",
  "TIKTOK_REFRESH_TOKEN",
  "YOUTUBE_CLIENT_ID",
  "YOUTUBE_CLIENT_SECRET",
  "YOUTUBE_REFRESH_TOKEN",
  "YOUTUBE_API_KEY",
  "TWITTER_API_KEY",
  "TWITTER_API_SECRET",
  "TWITTER_ACCESS_TOKEN",
  "TWITTER_ACCESS_SECRET",
  "META_USER_ACCESS_TOKEN",
  "META_APP_ID",
  "META_APP_SECRET",
  "IG_USER_ID",
  "PAYPAL_CLIENT_ID",
  "PAYPAL_CLIENT_SECRET",
  "PAYPAL_MODE",
  "AUTO_POST",
  "HUMAN_APPROVAL",
  "DAILY_POST_LIMIT",
  "DASHBOARD_PASSWORD",
  "SMTP_HOST",
  "SMTP_PORT",
  "SMTP_USER",
  "SMTP_PASS",
  "SMTP_FROM",
  "ALERT_EMAIL",
] as const;

interface Env {
  ASP_CONTAINER: DurableObjectNamespace<ASPContainer>;
  [key: string]: unknown;
}

export class ASPContainer extends DurableObject<Env> {
  private starting: Promise<void> | undefined;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    const container = ctx.container;
    if (container?.running) {
      void ctx.blockConcurrencyWhile(() =>
        container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS),
      );
    }
  }

  async fetch(request: Request): Promise<Response> {
    this.starting ??= this.startAndWaitForPort().finally(() => {
      this.starting = undefined;
    });
    await this.starting;

    const url = new URL(request.url);
    url.protocol = "http:";
    url.host = "container";
    const forwarded = new Request(url, request);
    forwarded.headers.delete("host");
    return this.ctx.container!.getTcpPort(CONTAINER_PORT).fetch(forwarded);
  }

  private async startAndWaitForPort(): Promise<void> {
    const container = this.ctx.container!;
    if (!container.running) {
      const env: Record<string, string> = { PORT: String(CONTAINER_PORT) };
      for (const key of FORWARDED_VARS) {
        const v = this.env[key];
        if (typeof v === "string" && v.length > 0) env[key] = v;
      }
      container.start({
        image: container.images.base,
        enableInternet: true,
        env,
      });
    }
    await container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS);

    const port = container.getTcpPort(CONTAINER_PORT);
    let lastError: unknown;
    for (let attempt = 0; attempt < 100; attempt++) {
      try {
        const res = await port.fetch("http://container/api/health", {
          signal: AbortSignal.timeout(2000),
        });
        await res.body?.cancel();
        if (!res.ok) throw new Error(`Health check returned ${res.status}`);
        return;
      } catch (error) {
        lastError = error;
        await scheduler.wait(500);
      }
    }
    throw new Error(
      `ASP container did not become ready on port ${CONTAINER_PORT}`,
      { cause: lastError },
    );
  }
}

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    // Pin ALL traffic to one instance — the app is stateful (local JSON).
    return env.ASP_CONTAINER.getByName(SINGLETON_NAME).fetch(request.clone());
  },
} satisfies ExportedHandler<Env>;
