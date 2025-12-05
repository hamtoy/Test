import { describe, expect, it, vi } from "vitest";
import { ApiError, apiCallWithRetry, parseSSEBuffer, withRetry } from "../utils.js";

describe("parseSSEBuffer", () => {
    it("parses complete SSE events and leaves no remainder", () => {
        const buffer = "data:{\"a\":1}\n\ndata:{\"b\":2}\n\n";
        const { events, remainder } = parseSSEBuffer(buffer);
        expect(events).toHaveLength(2);
        expect(events[0]).toEqual({ a: 1 });
        expect(events[1]).toEqual({ b: 2 });
        expect(remainder).toBe("");
    });

    it("keeps partial chunk in remainder", () => {
        const buffer = "data:{\"a\":1}\n\ndata:{\"b\":2}";
        const { events, remainder } = parseSSEBuffer(buffer);
        expect(events).toHaveLength(1);
        expect(events[0]).toEqual({ a: 1 });
        expect(remainder).toBe('data:{"b":2}');
    });
});

describe("withRetry", () => {
    it("retries on failures and eventually succeeds", async () => {
        let attempts = 0;
        const result = await withRetry(
            async () => {
                attempts += 1;
                if (attempts < 2) {
                    throw new ApiError(500);
                }
                return "ok";
            },
            2,
            10,
        );
        expect(result).toBe("ok");
        expect(attempts).toBe(2);
    });
});

describe("apiCallWithRetry", () => {
    it("retries failed responses and succeeds", async () => {
        const originalFetch = global.fetch;
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce({
                ok: false,
                status: 500,
                json: async () => ({ detail: "error" }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ ok: true }),
            });
        // @ts-expect-error - assign mock fetch
        global.fetch = fetchMock;

        const result = await apiCallWithRetry<{ ok: boolean }>({
            url: "/api/test",
            retries: 1,
            initialDelayMs: 1,
        });
        expect(result).toEqual({ ok: true });
        expect(fetchMock).toHaveBeenCalledTimes(2);

        global.fetch = originalFetch;
    });
});
