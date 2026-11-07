import { apiBaseUrl } from "./core";

export const assetsApi = {
  /** Direct URL for <audio src>, <video src>, etc. */
  contentUrl: (assetId: string) => `${apiBaseUrl()}/assets/${assetId}/content`,
  /** Same file, served as a download with the given file name. */
  downloadUrl: (assetId: string, fileName: string) =>
    `${apiBaseUrl()}/assets/${assetId}/content?download=${encodeURIComponent(fileName)}`,
};
