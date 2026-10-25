// Test-only import target. Production always imports cloudflare:sockets.
export function connect(): never { throw new Error('Unexpected SMTP access in a unit test'); }
