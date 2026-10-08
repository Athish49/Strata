import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";
import { mockApi } from "@/tests/support/mock-api";

// The app always talks to the live backend. Unit tests swap in an in-memory test double.
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...actual, api: mockApi };
});
