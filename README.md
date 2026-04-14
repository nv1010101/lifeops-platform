# LifeOps Platform

LifeOps Platform is a modular personal productivity platform with a FastAPI Platform Core, a Vue frontend shell, and remote modules that remain isolated behind explicit HTTP contracts.

## Repository layout

```text
lifeops-platform/
  platform-core/
  platform-frontend/
  nginx/
  docker-compose.yml
  specs/
```

## Slice 01 scope

This slice bootstraps the runtime only:

- FastAPI app factory with `GET /health`
- Vue 3 + Vite frontend shell
- backend and frontend smoke tests
- Ruff, ESLint, and Prettier configuration
- production-ready backend Dockerfile
- `docker-compose.yml` for Platform Core and PostgreSQL
- Nginx reverse proxy template

No business logic is implemented yet.

## Local backend setup

1. Create a virtual environment:

   ```bash
   cd platform-core
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Copy the example environment file and fill in values:

   ```bash
   cp .env.example .env
   cp .env.db.example .env.db
   ```

3. Install dependencies:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   ```

4. Run the API:

   ```bash
   uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
   ```

5. Run checks:

   ```bash
   pytest
   ruff check .
   ruff format --check .
   ```

## Local frontend setup

1. Install dependencies:

   ```bash
   cd platform-frontend
   npm install
   ```

2. Copy the example environment file and fill in values:

   ```bash
   cp .env.example .env
   ```

3. Start the development server:

   ```bash
   npm run dev
   ```

4. Run checks:

   ```bash
   npm run test
   npm run lint
   npm run format
   ```

## Production deployment

### Prerequisites

- Ubuntu LTS or similar Linux host
- Docker Engine and Docker Compose plugin
- Nginx
- DNS pointed at the server

### Server preparation

1. Clone the repository on the server:

   ```bash
   git clone <repository-url> /opt/lifeops/lifeops-platform
   cd /opt/lifeops/lifeops-platform
   ```

2. Create the runtime environment files:

   ```bash
   cp platform-core/.env.example platform-core/.env
   cp platform-core/.env.db.example platform-core/.env.db
   ```

3. Fill in real values in `platform-core/.env` and `platform-core/.env.db`.

4. Build the frontend bundle:

   ```bash
   cd platform-frontend
   npm install
   npm run build
   ```

5. Publish the frontend assets for Nginx:

   ```bash
   mkdir -p /var/www/lifeops-platform/current
   cp -R dist/* /var/www/lifeops-platform/current/
   ```

6. Start the backend and database:

   ```bash
   cd /opt/lifeops/lifeops-platform
   docker compose up -d --build
   ```

7. Install the Nginx template:

   ```bash
   cp nginx/nginx.conf /etc/nginx/sites-available/lifeops-platform.conf
   ln -s /etc/nginx/sites-available/lifeops-platform.conf /etc/nginx/sites-enabled/lifeops-platform.conf
   nginx -t && systemctl reload nginx
   ```

### Update procedure

Use the same deployment path for every update in this slice:

```bash
cd /opt/lifeops/lifeops-platform
git pull
docker compose up -d --build
```

If frontend assets changed:

```bash
cd /opt/lifeops/lifeops-platform/platform-frontend
npm install
npm run build
cp -R dist/* /var/www/lifeops-platform/current/
systemctl reload nginx
```

### Verification

After deploy, verify:

```bash
curl http://127.0.0.1:8000/health
curl https://your-domain.example/health
curl https://your-domain.example/api/health
docker compose ps
```

Expected health response:

```json
{"status":"ok","env":"production"}
```

## Public docs

- [Architecture](./ARCHITECTURE.md)
- [Module Contract](./MODULE_CONTRACT.md)
- [Roadmap](./ROADMAP.md)
