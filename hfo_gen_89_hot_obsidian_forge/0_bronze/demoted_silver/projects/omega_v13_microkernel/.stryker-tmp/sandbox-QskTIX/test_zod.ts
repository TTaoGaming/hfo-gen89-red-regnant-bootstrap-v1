// @ts-nocheck
import { PointerUpdateSchema } from './schemas';

console.log('Testing valid payload...');
try {
    PointerUpdateSchema.parse({
        handId: 0,
        x: 0.5,
        y: 0.5,
        isPinching: false
    });
    console.log('Valid payload passed.');
} catch (e: any) {
    console.error('Valid payload failed:', e);
}

console.log('\nTesting invalid payload (x out of bounds)...');
try {
    PointerUpdateSchema.parse({
        handId: 0,
        x: 1.5,
        y: 0.5,
        isPinching: false
    });
    console.log('Invalid payload passed (THIS IS A BUG).');
} catch (e: any) {
    console.log('Invalid payload caught successfully:');
    console.log(e.message);
}

console.log('\nTesting invalid payload (missing field)...');
try {
    PointerUpdateSchema.parse({
        handId: 0,
        x: 0.5,
        y: 0.5
    });
    console.log('Invalid payload passed (THIS IS A BUG).');
} catch (e: any) {
    console.log('Invalid payload caught successfully:');
    console.log(e.message);
}
