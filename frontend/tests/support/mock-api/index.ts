import type { StrataApi } from "@/lib/api/client";
import { companyApi } from "./company";
import { engineApi } from "./engine";
import { kbApi } from "./kb";

export { setMockLatency, isMockLatencyEnabled } from "./config";
export { resetMockState } from "./state";
export { CUSTOM_RUN_MS } from "./engine";

export const mockApi: StrataApi = { kb: kbApi, engine: engineApi, company: companyApi };
