FROM node:24-alpine AS config
WORKDIR /app
COPY links.json links.schema.json ./
COPY scripts ./scripts
COPY site ./site
RUN node scripts/build-links.mjs

FROM node:24-bookworm-slim
ARG APP_RELEASE_VERSION
ARG APP_RELEASE_ID
ENV APP_RELEASE_VERSION=$APP_RELEASE_VERSION APP_RELEASE_ID=$APP_RELEASE_ID HOME=/tmp PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN groupadd -g 101 nginx && useradd -u 101 -g nginx -M -s /usr/sbin/nologin nginx \
    && apt-get update && apt-get install -y --no-install-recommends nginx python3 python3-pil tzdata chromium ca-certificates wget fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data && chown nginx:nginx /data
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts \
    && node node_modules/playwright-core/cli.js install --with-deps firefox \
    && chmod -R a+rX /opt/playwright \
    && rm -rf /var/lib/apt/lists/* && npm cache clean --force
LABEL org.opencontainers.image.source="https://github.com/Mick7784/links"
LABEL org.opencontainers.image.title="Links"
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=config /app/site/ /usr/share/nginx/html/
COPY scripts/video-api.mjs scripts/start.mjs /app/
COPY scripts/analytics.py scripts/url_inspection.py scripts/tracked_batch.py scripts/tracked_links.py scripts/affiliate_partners.py scripts/short_urls.py scripts/instance.py scripts/youtube.py scripts/themes.py scripts/images.py scripts/storage.py links.json VERSION /app/
COPY scripts/pulse_manager.py scripts/descriptions.py scripts/description_analysis.py scripts/description_default.json /app/
COPY scripts/affiliation.py scripts/affiliation-worker.mjs scripts/affiliation-browser.mjs scripts/domadoo.mjs /app/
COPY admin/ /app/admin/
USER nginx
EXPOSE 8080 8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["node", "/app/start.mjs"]
