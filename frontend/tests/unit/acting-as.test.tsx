import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/app",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));
import type { ReactNode } from "react";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { mockApi, setMockLatency } from "@/tests/support/mock-api";
import { resetCompanyMock } from "@/tests/support/mock-api/company";
import { ACTOR_STORAGE_KEY, getActingPersonId, resetActorStoreForTests, setActingPersonId } from "@/lib/actor";
import type { OrgPerson } from "@/lib/api/schemas";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ACTING_AS_SELECTOR_ID } from "@/components/documents/upload/logic";
import { Sidebar } from "@/components/shell/Sidebar";
import { ShellProvider } from "@/components/shell/ShellContext";
import { ActingAsControl, ActingAsPrompt } from "@/components/shell/ActingAs";
import {
  NO_ACTOR_MESSAGE,
  activePeople,
  resetActingAsStoresForTests,
  resolveActor,
} from "@/components/shell/acting-as";

beforeAll(() => {
  // cmdk / Radix need these in jsdom.
  if (!("ResizeObserver" in globalThis)) {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
  }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
});

const person = (id: string, name: string, extra: Partial<OrgPerson> = {}): OrgPerson => ({
  person_id: id,
  name,
  title: `${name} title`,
  department: "Legal",
  department_id: null,
  reports_to_id: null,
  email: null,
  is_active: true,
  ...extra,
});
const PEOPLE: OrgPerson[] = [
  person("P01", "Ada Active", { title: "General Counsel", department: "Legal" }),
  person("P02", "Ivan Inactive", { is_active: false }),
  person("P03", "Bea Brown", { title: "Records Manager", department: "Operations" }),
];

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const W = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
  return W;
}

function people(list: OrgPerson[] = PEOPLE) {
  return vi.spyOn(mockApi.company, "listOrgPeople").mockResolvedValue(list);
}

beforeEach(() => {
  setMockLatency(false);
  resetCompanyMock();
  localStorage.clear();
  resetActorStoreForTests();
  resetActingAsStoresForTests();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
  resetActorStoreForTests();
  resetActingAsStoresForTests();
});

describe("acting-as logic", () => {
  it("activePeople drops inactive people and sorts by name", () => {
    expect(activePeople(PEOPLE).map((p) => p.person_id)).toEqual(["P01", "P03"]);
    expect(activePeople(undefined)).toEqual([]);
  });
  it("resolveActor: none / loading / ok / stale (inactive, missing) / unverified", () => {
    expect(resolveActor(null, PEOPLE).status).toBe("none");
    expect(resolveActor("P01", undefined).status).toBe("loading");
    expect(resolveActor("P01", undefined, true)).toEqual({ status: "unverified", id: "P01" });
    expect(resolveActor("P01", PEOPLE)).toMatchObject({ status: "ok", person: { name: "Ada Active" } });
    expect(resolveActor("P02", PEOPLE)).toMatchObject({ status: "stale", stale: { reason: "inactive", name: "Ivan Inactive" } });
    expect(resolveActor("P99", PEOPLE)).toMatchObject({ status: "stale", stale: { reason: "missing", name: null } });
  });
});

describe("<ActingAsControl />", () => {
  it("lists active people only, with title and department", async () => {
    people();
    const user = userEvent.setup();
    render(<ActingAsControl />, { wrapper: wrapper() });
    const trigger = await screen.findByRole("button", { name: NO_ACTOR_MESSAGE });
    expect(trigger).toHaveAttribute("id", "acting-as");
    await user.click(trigger);
    const list = await screen.findByRole("listbox");
    const opts = within(list).getAllByRole("option");
    expect(opts.map((o) => o.textContent)).toEqual([
      expect.stringContaining("Ada Active"),
      expect.stringContaining("Bea Brown"),
    ]);
    expect(opts[0]).toHaveTextContent("General Counsel · Legal");
    expect(within(list).queryByText("Ivan Inactive")).toBeNull();
  });

  it("selecting persists, announces, and survives a reload (store re-created)", async () => {
    people();
    const user = userEvent.setup();
    const { unmount } = render(<ActingAsControl />, { wrapper: wrapper() });
    await user.click(await screen.findByRole("button", { name: NO_ACTOR_MESSAGE }));
    await user.click(await screen.findByRole("option", { name: /Bea Brown/ }));
    expect(getActingPersonId()).toBe("P03");
    expect(localStorage.getItem(ACTOR_STORAGE_KEY)).toBe("P03");
    expect(await screen.findByRole("button", { name: /Acting as Bea Brown, Records Manager/ })).toBeInTheDocument();
    expect(screen.getByText("Now acting as Bea Brown, Records Manager.")).toBeInTheDocument();
    unmount();

    resetActorStoreForTests(); // simulates a reload: memory gone, storage remains
    render(<ActingAsControl />, { wrapper: wrapper() });
    expect(await screen.findByRole("button", { name: /Acting as Bea Brown/ })).toBeInTheDocument();
    expect(screen.getByText("Records Manager · Operations")).toBeInTheDocument();
  });

  it("is keyboard operable", async () => {
    people();
    const user = userEvent.setup();
    render(<ActingAsControl />, { wrapper: wrapper() });
    await screen.findByRole("button", { name: NO_ACTOR_MESSAGE });
    await user.tab();
    expect(screen.getByRole("button", { name: NO_ACTOR_MESSAGE })).toHaveFocus();
    await user.keyboard("{Enter}");
    await screen.findByRole("listbox");
    await user.keyboard("{ArrowDown}{Enter}");
    await waitFor(() => expect(getActingPersonId()).not.toBeNull());
  });

  it("treats a stale stored id as unset, clears it, and says so", async () => {
    people();
    setActingPersonId("P02"); // inactive
    render(<ActingAsControl />, { wrapper: wrapper() });
    expect(await screen.findByText("Ivan Inactive is no longer active.")).toBeInTheDocument();
    expect(getActingPersonId()).toBeNull();
    expect(localStorage.getItem(ACTOR_STORAGE_KEY)).toBeNull();
    expect(screen.getByText(NO_ACTOR_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(`Ivan Inactive is no longer active. ${NO_ACTOR_MESSAGE}`);
  });

  it("a deleted person is also dropped", async () => {
    people();
    setActingPersonId("P99");
    render(<ActingAsControl />, { wrapper: wrapper() });
    expect(await screen.findByText("Person P99 is no longer in the directory.")).toBeInTheDocument();
    expect(getActingPersonId()).toBeNull();
  });

  it("never clears the stored id when the people list fails to load", async () => {
    vi.spyOn(mockApi.company, "listOrgPeople").mockRejectedValue(new Error("down"));
    setActingPersonId("P01");
    render(<ActingAsControl />, { wrapper: wrapper() });
    expect(await screen.findByText("Couldn't load the directory")).toBeInTheDocument();
    expect(getActingPersonId()).toBe("P01");
  });

  it("renders when localStorage throws (selection kept in memory)", async () => {
    people();
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    const user = userEvent.setup();
    render(<ActingAsControl />, { wrapper: wrapper() });
    await user.click(await screen.findByRole("button", { name: NO_ACTOR_MESSAGE }));
    await user.click(await screen.findByRole("option", { name: /Ada Active/ }));
    expect(await screen.findByRole("button", { name: /Acting as Ada Active/ })).toBeInTheDocument();
  });

  it("renders when the localStorage accessor itself throws", async () => {
    people();
    const desc = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new DOMException("denied", "SecurityError");
      },
    });
    try {
      const user = userEvent.setup();
      render(<ActingAsControl />, { wrapper: wrapper() });
      await user.click(await screen.findByRole("button", { name: NO_ACTOR_MESSAGE }));
      await user.click(await screen.findByRole("option", { name: /Bea Brown/ }));
      expect(await screen.findByRole("button", { name: /Acting as Bea Brown/ })).toBeInTheDocument();
      expect(getActingPersonId()).toBe("P03");
    } finally {
      if (desc) Object.defineProperty(window, "localStorage", desc);
    }
  });

  it("collapsed rail shows the actor's initials with an accessible name", async () => {
    people();
    setActingPersonId("P01");
    render(<ActingAsControl collapsed />, { wrapper: wrapper() });
    const b = await screen.findByRole("button", { name: /Acting as Ada Active, General Counsel/ });
    expect(b).toHaveTextContent("AA");
  });

  it("shows a search box when the list is long", async () => {
    people(Array.from({ length: 12 }, (_, i) => person(`Q${i}`, `Person ${String.fromCharCode(65 + i)}`)));
    const user = userEvent.setup();
    render(<ActingAsControl />, { wrapper: wrapper() });
    await user.click(await screen.findByRole("button", { name: NO_ACTOR_MESSAGE }));
    await user.type(await screen.findByPlaceholderText("Search people…"), "Person C");
    await waitFor(() => expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([expect.stringContaining("Person C")]));
  });
});

describe("shell mount", () => {
  it("the rendered sidebar (expanded and rail) carries the #acting-as target next to the company chip", async () => {
    people();
    setActingPersonId("P01");
    const W = wrapper();
    render(
      <W>
        <ShellProvider>
          <Sidebar />
        </ShellProvider>
      </W>,
    );
    await screen.findByRole("button", { name: /Acting as Ada Active/ });
    const el = document.getElementById(ACTING_AS_SELECTOR_ID);
    expect(el).not.toBeNull();
    expect(el).toHaveAccessibleName(/Acting as Ada Active, General Counsel/);
    expect(document.querySelectorAll(`#${ACTING_AS_SELECTOR_ID}`)).toHaveLength(1);
    expect(screen.getByText("Rockridge Power & Light")).toBeInTheDocument();
  });
});

describe("<ActingAsPrompt />", () => {
  it("prompts when nobody is selected and disappears once someone is chosen", async () => {
    people();
    const user = userEvent.setup();
    render(<ActingAsPrompt />, { wrapper: wrapper() });
    expect(await screen.findByText(NO_ACTOR_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Choose person" }));
    await user.click(await screen.findByRole("option", { name: /Ada Active/ }));
    await waitFor(() => expect(screen.queryByText(NO_ACTOR_MESSAGE)).toBeNull());
    expect(getActingPersonId()).toBe("P01");
  });

  it("renders nothing while a valid actor is set", async () => {
    people();
    setActingPersonId("P01");
    const { container } = render(<ActingAsPrompt />, { wrapper: wrapper() });
    await waitFor(() => expect(mockApi.company.listOrgPeople).toHaveBeenCalled());
    await act(async () => {});
    expect(container).not.toHaveTextContent(NO_ACTOR_MESSAGE);
  });
});

describe("hydration", () => {
  it("server markup matches the first client render (no mismatch, no flash of a name or prompt)", async () => {
    people();
    setActingPersonId("P01");
    const W = wrapper();
    const tree = (
      <W>
        <ActingAsControl />
        <ActingAsPrompt />
      </W>
    );
    const html = renderToString(tree);
    expect(html).not.toContain("Ada Active");
    expect(html).not.toContain(NO_ACTOR_MESSAGE);

    const el = document.createElement("div");
    el.innerHTML = html;
    document.body.appendChild(el);
    const onRecoverableError = vi.fn();
    const consoleError = vi.spyOn(console, "error");
    let root: ReturnType<typeof hydrateRoot> | undefined;
    await act(async () => {
      root = hydrateRoot(el, tree, { onRecoverableError });
    });
    await waitFor(() => expect(el).toHaveTextContent("Ada Active"));
    expect(onRecoverableError).not.toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
    expect(el).not.toHaveTextContent(NO_ACTOR_MESSAGE);
    act(() => root?.unmount());
    el.remove();
  });
});
