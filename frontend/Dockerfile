FROM node:22-alpine

WORKDIR /app

RUN npm install -g pnpm@11.2.2

ENV CI=true

COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile \
    --fetch-retries=5 \
    --network-concurrency=10

COPY . .

EXPOSE 5173

CMD ["pnpm", "run", "dev", "--host"]