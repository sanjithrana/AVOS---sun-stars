import { api } from "./core";
import type { ModelsStatus } from "@/types";

export const modelsApi = {
  /** The AVOS model catalog (image / video / avatar / control) with what is ready to run now. */
  list: () => api.get<ModelsStatus>("/models"),
};
