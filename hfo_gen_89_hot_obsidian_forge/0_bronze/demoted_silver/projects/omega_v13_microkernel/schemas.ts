import { z } from 'zod';

// ATDD-ARCH-004: Runtime Syntactic Enforcement for W3C Pointer Fabric
// The Host (MediaPipe) must send strictly validated data to the Guest (W3C Fabric)

export const PointerUpdateSchema = z.object({
    handId: z.number().int().nonnegative(),
    x: z.number().min(0).max(1), // Normalized coordinates
    y: z.number().min(0).max(1),
    isPinching: z.boolean()
});

export const PointerCoastSchema = z.object({
    handId: z.number().int().nonnegative(),
    isPinching: z.boolean(),
    destroy: z.boolean()
});

export type PointerUpdatePayload = z.infer<typeof PointerUpdateSchema>;
export type PointerCoastPayload = z.infer<typeof PointerCoastSchema>;
