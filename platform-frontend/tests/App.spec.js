import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../src/App.vue";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("mounts the bootstrap shell", () => {
    vi.stubEnv("VITE_APP_NAME", "");

    const wrapper = mount(App);

    expect(wrapper.text()).toContain("LifeOps Platform");
    expect(wrapper.text()).toContain("FastAPI /health");
  });
});
