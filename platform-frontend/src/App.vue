<template>
  <main class="app-shell">
    <section class="hero-card">
      <p class="eyebrow">Slice 01</p>
      <h1>{{ appName }}</h1>
      <p class="summary">
        Platform shell bootstrap is online. Backend health and frontend runtime
        are wired and ready for the next slice.
      </p>
      <dl class="status-grid">
        <div>
          <dt>Frontend</dt>
          <dd>Vue 3 + Vite</dd>
        </div>
        <div>
          <dt>Backend</dt>
          <dd>FastAPI /health</dd>
        </div>
        <div>
          <dt>API Base</dt>
          <dd>{{ apiBaseUrl }}</dd>
        </div>
      </dl>
    </section>
  </main>
</template>

<script setup>
const appName = import.meta.env.VITE_APP_NAME || "LifeOps Platform";
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "/api";
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  margin: 0;
  padding: 2rem;
  background: radial-gradient(
      circle at top,
      rgba(255, 196, 122, 0.2),
      transparent 28rem
    ),
    linear-gradient(135deg, #f7f1e8, #e8eef4);
  color: #1f2933;
}

.hero-card {
  width: min(100%, 46rem);
  padding: 2.5rem;
  border: 1px solid rgba(31, 41, 51, 0.08);
  border-radius: 1.5rem;
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 1.5rem 4rem rgba(31, 41, 51, 0.08);
  backdrop-filter: blur(12px);
}

.eyebrow {
  margin: 0 0 0.75rem;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #a34a28;
}

h1 {
  margin: 0;
  font-size: clamp(2.2rem, 6vw, 4rem);
  line-height: 0.95;
}

.summary {
  margin: 1.25rem 0 0;
  max-width: 42rem;
  font-size: 1.05rem;
  line-height: 1.6;
  color: #52606d;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: 1rem;
  margin: 2rem 0 0;
}

.status-grid div {
  padding: 1rem;
  border-radius: 1rem;
  background: rgba(247, 241, 232, 0.9);
}

dt {
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #7b8794;
}

dd {
  margin: 0.4rem 0 0;
  font-size: 1rem;
  font-weight: 600;
}
</style>
