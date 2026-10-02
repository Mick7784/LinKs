FROM node:24-alpine AS config
WORKDIR /app
COPY links.json links.schema.json ./
COPY scripts ./scripts
COPY site ./site
RUN node scripts/build-links.mjs

FROM nginx:stable-alpine
ARG APP_RELEASE_VERSION
ARG APP_RELEASE_ID
ENV APP_RELEASE_VERSION=$APP_RELEASE_VERSION APP_RELEASE_ID=$APP_RELEASE_ID
RUN apk add --no-cache nodejs python3 tzdata
RUN mkdir -p /data && chown nginx:nginx /data
LABEL org.opencontainers.image.source="https://github.com/Mick7784/links"
LABEL org.opencontainers.image.title="Links"
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=config /app/site/ /usr/share/nginx/html/
COPY scripts/video-api.mjs scripts/start.mjs /app/
COPY scripts/analytics.py scripts/instance.py links.json VERSION /app/
COPY admin/ /app/admin/
USER nginx
EXPOSE 8080 8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["node", "/app/start.mjs"]
