import { describe, expect, it } from "vitest";

import { AtlasApiError } from "./api-error";

describe("AtlasApiError", () => {
  it("preserves stable API error metadata for server actions", () => {
    const error = new AtlasApiError(
      "Access denied.",
      403,
      "forbidden",
      "24f4ca40-25dd-4112-8285-03089988002d",
    );

    expect(error).toBeInstanceOf(Error);
    expect(error.name).toBe("AtlasApiError");
    expect(error.status).toBe(403);
    expect(error.code).toBe("forbidden");
    expect(error.requestId).toBe("24f4ca40-25dd-4112-8285-03089988002d");
  });
});
