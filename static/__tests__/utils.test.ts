import { describe, expect, it } from "vitest";
import { ApiError, parseSSEBuffer, withRetry } from "../utils.js";

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
