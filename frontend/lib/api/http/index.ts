import type { StrataApi } from "../client";
import { companyHttp } from "./company";
import { engineHttp } from "./engine";
import { kbHttp } from "./kb";

export const httpApi: StrataApi = { kb: kbHttp, engine: engineHttp, company: companyHttp };
