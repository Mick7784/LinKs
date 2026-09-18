FROM node:24-alpine AS config
WORKDIR /app
COPY links.json links.schema.json ./
COPY scripts ./scripts
COPY site ./site
RUN node scripts/build-links.mjs

FROM nginx:stable-alpine
LABEL org.opencontainers.image.source="https://github.com/Mick7784/links"
LABEL org.opencontainers.image.title="DomotiK Studio Links"
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=config /app/site/ /usr/share/nginx/html/
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
