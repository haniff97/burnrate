import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { createId } from './dist/ids.mjs';

const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
// Simulate a LAN HTTP browser: secure random bytes, but no randomUUID method.
const lanCrypto = { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) };
const ids = Array.from({ length: 1000 }, () => createId(lanCrypto));
assert.ok(ids.every(id => uuidV4.test(id)));
assert.equal(new Set(ids).size, ids.length);
assert.equal(createId({ getRandomValues: bytes => bytes.fill(0) }), '00000000-0000-4000-8000-000000000000');
let nativeCalls = 0;
assert.equal(createId({ randomUUID() { nativeCalls++; return 'native-id'; } }), 'native-id');
assert.equal(nativeCalls, 1);
console.log('Passed LAN HTTP UUID fallback and native UUID checks.');
